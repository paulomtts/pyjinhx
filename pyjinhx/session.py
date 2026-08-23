"""RenderSession, the per-request ContextVars, and the request_scope that owns them."""

import threading
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import BaseLoader, Environment, TemplateNotFound

from pyjinhx.assets import AssetMode
from pyjinhx.markers import finalize_slot_node

if TYPE_CHECKING:
    # Type-only: the hook's signature names the spine's own types, but importing
    # them at runtime would point session at its own consumers.
    from pyjinhx._component import BaseComponent

    # Type-only for the same reason config is imported inside request_scope()'s
    # body and nowhere else: config sits above the render spine, so a runtime
    # module-scope edge back would be a genuine cycle.
    from pyjinhx.config import PjxSettings
    from pyjinhx.segments import RenderedLevel

# The eight pieces of per-request mutable state. They live here rather than
# beside their eventual consumers because the import rule runs one way only:
# reactive/ imports session, never the reverse. Each defaults to None so that
# reading one outside a request is a miss, not a LookupError.
_render_session: ContextVar["RenderSession | None"] = ContextVar(
    "pjx_render_session", default=None
)
_instances: ContextVar[dict[str, object] | None] = ContextVar(
    "pjx_instances", default=None
)
_dirtied: ContextVar[set[str] | None] = ContextVar("pjx_dirtied", default=None)
_cache_store: ContextVar[dict[object, object] | None] = ContextVar(
    "pjx_cache_store", default=None
)
_cache_reverse: ContextVar[dict[str, set[tuple[type, object]]] | None] = ContextVar(
    "pjx_cache_reverse", default=None
)
_cache_forward: ContextVar[dict[tuple[type, object], set[str]] | None] = ContextVar(
    "pjx_cache_forward", default=None
)
_load_context: ContextVar[object | None] = ContextVar("pjx_load_context", default=None)
_freshness_cache: ContextVar[dict[str, bool] | None] = ContextVar(
    "pjx_freshness_cache", default=None
)

# Not a ContextVar and deliberately so: this mirrors dev._dev_config, which is
# process-wide configuration rather than per-request state, so it stays out of
# invariant 4's per-request mutable-state census. dev owns the policy; session
# holds the bit because registry sits below dev and may not import it. Per
# invariant 4 ("built-then-swapped under a lock, or ContextVar-scoped — no
# third category"), a bare module global takes the lock branch, matching
# _environment_cache_lock further down this file.
_dev_strict = False
_dev_strict_lock = threading.Lock()


class NoActiveRequestScope(RuntimeError):
    """Raised when per-request state is touched outside an active request_scope()."""


class AbsolutePathLoader(BaseLoader):
    """Jinja loader that treats every template name as an absolute filesystem path."""

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str, Callable[[], bool]]:
        # Absolute-only, with no search root and no relative fallback, because
        # component template names are already fully resolved by
        # _resolve_template_path - there is nothing left to search for. A
        # fallback rooted at cwd would silently load whichever file happened to
        # sit beside the process, which is how the old FileSystemLoader("templates")
        # default turned every un-configured request into a TemplateNotFound (#728).
        path = Path(template)
        if not path.is_absolute() or not path.is_file():
            raise TemplateNotFound(template)
        source = path.read_text(encoding="utf-8")
        mtime = path.stat().st_mtime
        name = str(path)

        def uptodate() -> bool:
            # One stat per template per request, not one per lookup. Jinja calls
            # this on every get_template() when auto_reload is on, and a reactive
            # request's walk_manifest() looks the same template up once per dirty
            # candidate - hundreds of identical stats for one file. The request
            # cache is a plain dict bound once by request_scope(), so the fan-out
            # threadpool's per-item Context copies all mutate the same object.
            freshness = get_freshness_cache()
            if freshness.get(name):
                return True
            # Matches FileSystemLoader's cache-invalidation contract: a deleted
            # or touched file must invalidate, so the missing case is stale
            # rather than an exception escaping Jinja's cache check. Only the
            # confirmed-fresh answer is worth remembering; a stale one has to be
            # re-asked, since the reload it triggers changes the answer.
            try:
                fresh = path.stat().st_mtime == mtime
            except OSError:
                return False
            if fresh:
                freshness[name] = True
            return fresh

        return source, name, uptodate


def _build_environment(
    jinja_globals: Mapping[str, Any] | None,
    jinja_filters: Mapping[str, Any] | None,
) -> Environment:
    """A new Jinja environment with pyjinhx's loader, autoescape and slot finalize."""
    env = Environment(
        loader=AbsolutePathLoader(),
        autoescape=True,
        # Interpolating a component-valued slot must not stringify it; the
        # hook swaps in a placeholder the render pipeline resolves later.
        finalize=finalize_slot_node,
    )
    # update(), never assignment: Jinja seeds both mappings with its own
    # builtins (range, dict, |upper, |length ...) and replacing the mapping
    # outright would take a template's whole standard library with it.
    # None is "nothing to add", not "clear".
    if jinja_globals is not None:
        env.globals.update(jinja_globals)
    if jinja_filters is not None:
        env.filters.update(jinja_filters)
    return env


# Keyed by id(settings) rather than by the settings object, because PjxSettings
# is a frozen dataclass: two distinct instances with equal fields hash and
# compare equal, and one carrying a plain dict in jinja_globals is not hashable
# at all. Identity is what an environment's contents actually depend on. The
# settings object is stored beside its environment so CPython cannot recycle
# its id onto a different object while the entry is live.
_environment_cache: dict[int, tuple["PjxSettings", Environment]] = {}
# architecture-overview.md invariant 4: process-wide mutable state is either
# built-then-swapped under a lock, or ContextVar-scoped - no third category.
# This dict is mutated in place (not swapped), so the lock has to wrap every
# read-or-build, matching classless.py's _build_lock / discovery.py's
# _registry_lock shape. Without it, two threads racing the first lookup for
# one settings instance could each build and store their own Environment,
# and a session already handed the loser would render off a discarded one -
# silently breaking "one environment per settings" under the exact
# concurrency this cache exists to survive.
_environment_cache_lock = threading.Lock()


def _environment_for(settings: "PjxSettings") -> Environment:
    """The process-wide Jinja environment for ``settings``, built on first use.

    Every request served under one settings object shares one environment.
    Building a fresh one per request threw away Jinja's template cache — which
    lives on the environment — so every request re-read and re-compiled every
    template it touched.
    """
    with _environment_cache_lock:
        cached = _environment_cache.get(id(settings))
        if cached is not None:
            return cached[1]
        env = _build_environment(settings.jinja_globals, settings.jinja_filters)
        _environment_cache[id(settings)] = (settings, env)
        return env


class RenderSession:
    """Session providing Jinja environment with autoescape enabled."""

    def __init__(
        self,
        *,
        jinja_env: Environment | None = None,
        jinja_globals: Mapping[str, Any] | None = None,
        jinja_filters: Mapping[str, Any] | None = None,
    ):
        """Initialize render session, optionally with extra Jinja globals and filters.

        ``jinja_env`` adopts an already-built environment: this is how the two
        request paths hand in the process-wide cached one instead of paying for
        a fresh environment — and a cold template cache — per request. It is
        mutually exclusive with the two mappings, which build a private
        environment for a session the caller assembles by hand.
        """
        if jinja_env is not None and (
            jinja_globals is not None or jinja_filters is not None
        ):
            raise TypeError(
                "pass jinja_env or jinja_globals/jinja_filters, not both: an "
                "adopted environment is shared with every other session built "
                "from the same settings, so updating it here would leak this "
                "session's names into all of them."
            )
        self.jinja_env = (
            jinja_env
            if jinja_env is not None
            else _build_environment(jinja_globals, jinja_filters)
        )
        # Generic per-request asset slot from the #423 ContextVar model
        # (predates L2.2.1's descriptor accumulator below); no producer in
        # this codebase writes to it yet, so it stays as-is for whatever
        # future non-descriptor asset source needs a request-scoped set.
        self.asset_paths: set[str] = set()
        # css_assets/js_assets are the L2.2.1 accumulator: descriptor paths
        # set-added by accumulate_assets as on_rendered fires, kept separate
        # from each other so later emission (#430) can tell <style> from
        # <script> sources without re-inspecting any descriptor.
        self.css_assets: set[Path] = set()
        self.js_assets: set[Path] = set()
        # Per-kind delivery mode for this render. INLINE by default so a cold
        # render works with no configuration; NONE is how a caller that ships
        # assets some other way (a build step, a CDN) suppresses emission.
        self.css_mode: AssetMode = AssetMode.INLINE
        self.js_mode: AssetMode = AssetMode.INLINE
        # The pjx.js + htmx payload for this render, set by client/inject.py and
        # read by emit_assets. Kept off css_assets/js_assets because those hold
        # file paths from component descriptors, while this is source text with
        # no path of its own. The flag is what makes a nested render — or a
        # second inject_runtime call on the same session — a no-op.
        self.runtime_script: str | None = None
        # The always-on runtime CSS block, emitted with the other <style> tags
        # so runtime_script stays a single pure <script>.
        self.runtime_style: str | None = None
        self.runtime_injected: bool = False
        # Re-entrancy depth for render(): a nested .render() (a parent
        # stringifying a child mid-build) sees depth > 0 and skips emission, so
        # the bundle and the asset tags land once, at the outermost return.
        # A counter rather than a once-ever flag on purpose: two *independent*
        # top-level renders in one session each start and end at depth 0 and
        # each still get their assets, as they do today.
        self.render_depth: int = 0
        # A plain list, not an event bus: render fires it once per component and
        # subscribers (asset accumulation, the reactive instance registry) just
        # append. Per-session so subscriptions die with the request. Callbacks
        # take the session itself as a third argument — never the request_scope
        # ContextVar, which the render() caller may not have entered at all —
        # since accumulate_assets is registered directly (not via a closure)
        # and needs a session reference to write into.
        self.on_rendered: list[
            Callable[[BaseComponent, RenderedLevel, RenderSession], None]
        ] = []
        # The Starlette request object for this render, set by middleware and
        # read by PjxContext to expose app context. Manifests live on the
        # session itself (pjx_mounted/pjx_assets/pjx_trigger below), not on
        # request.state.
        self.pjx_request: Any = None
        # The parsed pjx request headers. They live on the session, not on
        # request.state, because the response composer is framework-free: it
        # has no Request to read manifests from, only the active session.
        self.pjx_mounted: list[dict[str, Any]] = []
        self.pjx_assets: frozenset[str] = frozenset()
        self.pjx_trigger: dict[str, Any] | None = None
        # Per-request map of reactive instance id -> that class's
        # _pjx_react_keys, written by reactive.root_attrs.record_nested_react_keys
        # when a caller appends it to on_rendered above. #1013's fan-out reads it
        # to decide which nested reactive regions a parent swap must retain, so
        # the key is the same instance-id string fanout's _contained resolves
        # (ChildRef.attrs["id"] / _root_instance_id). Lives on the session, not
        # module-global: it must die with the request.
        self.nested_react_keys: dict[str, tuple[str, ...]] = {}

    def emit_rendered(self, component: "BaseComponent", level: "RenderedLevel") -> None:
        """Notify subscribers that ``component``'s subtree finished rendering.

        Args:
            component: The instance whose level just completed.
            level: That component's RenderedLevel, children and slots spliced in.
        """
        # Exceptions propagate: a subscriber that fails has left session state
        # half-written, and a render that silently drops an asset or a registry
        # entry is worse than one that stops.
        for callback in self.on_rendered:
            callback(component, level, self)


def current_session() -> RenderSession | None:
    """Return the RenderSession bound to this request, or None outside a scope."""
    return _render_session.get()


def accumulate_assets(
    component: Any, level: "RenderedLevel", session: "RenderSession"
) -> None:
    """Set-add the rendered class's descriptor asset paths into the session.

    Meant to be subscribed onto ``RenderSession.on_rendered``. Paths are read
    straight from the frozen descriptor and never re-probed; duplicates across
    instances or classes collapse because the store is a set keyed by path.

    Writes into ``session`` — the RenderSession that actually drove this
    render, passed through by render_level() — rather than reading
    ``current_session()``. render(component, session) is the dominant calling
    convention in this codebase and never requires the session to also be the
    active request_scope(), so accumulate_assets must not either.

    Args:
        component: The component that was just rendered (unused; on_rendered's
            callback shape always passes it).
        level: The RenderedLevel carrying the class descriptor.
        session: The RenderSession this render ran against.
    """
    # RenderedLevel.descriptor is typed as `object` to keep segments.py
    # import-pure; read structurally here rather than importing ClassDescriptor.
    descriptor: Any = level.descriptor
    session.css_assets.update(descriptor.css_paths)
    session.js_assets.update(descriptor.js_paths)


def get_instances() -> dict[str, object]:
    """Return this request's instance registry, or an empty dict outside a scope."""
    registry = _instances.get()
    if registry is None:
        return {}
    return registry


def get_dev_strict() -> bool:
    """Return whether reactive-dev strict mode is on, process-wide."""
    with _dev_strict_lock:
        return _dev_strict


def set_dev_strict(strict: bool) -> None:
    """Record whether reactive-dev strict mode is on.

    Args:
        strict: True while dev.enable_reactive_dev(strict=True) is in effect.
    """
    global _dev_strict
    with _dev_strict_lock:
        _dev_strict = strict


def get_dirtied() -> set[str]:
    """Return this request's dirtied reactive keys, or an empty set outside a scope."""
    dirtied = _dirtied.get()
    if dirtied is None:
        return set()
    return dirtied


def add_dirtied(keys: Iterable[str]) -> None:
    """Add already-normalized reactive keys to this request's dirtied set.

    Args:
        keys: Normalized string keys, as produced by coerce_reactive_keys().
    """
    dirtied = _dirtied.get()
    # Outside a request_scope() there is nothing to dirty and nothing that will
    # read it back; mirror get_dirtied()'s tolerance instead of raising.
    if dirtied is None:
        return
    dirtied.update(keys)


def get_cache_store() -> dict[object, object]:
    """Return this request's load cache store, or an empty dict outside a scope."""
    store = _cache_store.get()
    if store is None:
        return {}
    return store


def get_cache_reverse() -> dict[str, set[tuple[type, object]]]:
    """Return this request's reactive-key -> cache-entry index, empty outside a scope.

    Maps a normalized reactive key to the set of ``(cls, key)`` cache entries
    whose load depended on it, so dirtying a key can find exactly what to evict.
    """
    reverse = _cache_reverse.get()
    if reverse is None:
        return {}
    return reverse


def get_cache_forward() -> dict[tuple[type, object], set[str]]:
    """Return this request's cache-entry -> reactive-key index, empty outside a scope.

    The mirror of get_cache_reverse(): maps a ``(cls, key)`` cache entry to the
    set of reactive keys it was registered under, so un-indexing an entry can go
    straight to the buckets that hold it instead of scanning every bucket.
    """
    forward = _cache_forward.get()
    if forward is None:
        return {}
    return forward


def get_freshness_cache() -> dict[str, bool]:
    """Return this request's confirmed-fresh template paths, empty outside a scope.

    Keyed by the absolute template path string the loader reports as a Template's
    filename. A path recorded here has had its mtime confirmed once this request
    and is not re-stat'ed again until the next one, so a template edited mid-request
    is picked up on the following request rather than the current one.
    """
    cache = _freshness_cache.get()
    if cache is None:
        return {}
    return cache


def get_load_context() -> object | None:
    """Return whatever the app's ``context_factory`` produced for this request.

    None outside a request_scope(), and None inside one that was entered
    without a ``load_context`` - an app with no factory configured is the
    normal case, not an error.
    """
    return _load_context.get()


@contextmanager
def request_scope(
    session: "RenderSession | None" = None,
    *,
    load_context: object | None = None,
) -> Iterator[RenderSession]:
    """Bind fresh per-request state for the duration of the block.

    Args:
        session: An existing RenderSession to bind as this scope's current
            session, instead of constructing a fresh one. Lets a caller wire
            hooks (e.g. ``on_rendered``) onto a session before it becomes the
            one ``current_session()`` sees as active.
        load_context: The app's ``context_factory`` result for this request,
            readable for the life of the scope via ``get_load_context()``.
            None means "not supplied": the enclosing scope's value, if any,
            stays visible.

    Yields:
        The RenderSession bound for this scope.
    """
    if session is None:
        # Function-local by necessity: config sits above the render spine and
        # imports it at import time, so a module-scope edge back would be a
        # real cycle. Same escape hatch _component.py uses for rendering.py.
        # Only the branch that builds the session consults the settings: a
        # caller that supplied one already chose its environment.
        from pyjinhx.config import current_settings

        settings = current_settings()
        session = RenderSession(jinja_env=_environment_for(settings))
    session_token = _render_session.set(session)
    instances_token = _instances.set({})
    dirtied_token = _dirtied.set(set())
    cache_token = _cache_store.set({})
    cache_reverse_token = _cache_reverse.set({})
    cache_forward_token = _cache_forward.set({})
    freshness_token = _freshness_cache.set({})
    # Bound only when supplied, so an inner scope that knows nothing about the
    # app context cannot blank out the request's value for the code below it.
    load_token = _load_context.set(load_context) if load_context is not None else None
    try:
        yield session
    finally:
        # Reset by token rather than assigning None: a nested scope must hand the
        # outer scope its own state back, not clear the variable outright.
        if load_token is not None:
            _load_context.reset(load_token)
        _freshness_cache.reset(freshness_token)
        _cache_forward.reset(cache_forward_token)
        _cache_reverse.reset(cache_reverse_token)
        _cache_store.reset(cache_token)
        _dirtied.reset(dirtied_token)
        _instances.reset(instances_token)
        _render_session.reset(session_token)
