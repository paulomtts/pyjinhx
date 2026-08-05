"""RenderSession, the per-request ContextVars, and the request_scope that owns them."""

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
    from pyjinhx.segments import RenderedLevel

# The seven pieces of per-request mutable state. They live here rather than
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

        def uptodate() -> bool:
            # Matches FileSystemLoader's cache-invalidation contract: a deleted
            # or touched file must invalidate, so the missing case is stale
            # rather than an exception escaping Jinja's cache check.
            try:
                return path.stat().st_mtime == mtime
            except OSError:
                return False

        return source, str(path), uptodate


class RenderSession:
    """Session providing Jinja environment with autoescape enabled."""

    def __init__(
        self,
        *,
        jinja_globals: Mapping[str, Any] | None = None,
        jinja_filters: Mapping[str, Any] | None = None,
    ):
        """Initialize render session, optionally with extra Jinja globals and filters."""
        self.jinja_env = Environment(
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
            self.jinja_env.globals.update(jinja_globals)
        if jinja_filters is not None:
            self.jinja_env.filters.update(jinja_filters)
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
        session = RenderSession()
    session_token = _render_session.set(session)
    instances_token = _instances.set({})
    dirtied_token = _dirtied.set(set())
    cache_token = _cache_store.set({})
    cache_reverse_token = _cache_reverse.set({})
    cache_forward_token = _cache_forward.set({})
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
        _cache_forward.reset(cache_forward_token)
        _cache_reverse.reset(cache_reverse_token)
        _cache_store.reset(cache_token)
        _dirtied.reset(dirtied_token)
        _instances.reset(instances_token)
        _render_session.reset(session_token)
