"""RenderSession, the per-request ContextVars, and the request_scope that owns them."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader

from pyjinhx2.assets import AssetMode
from pyjinhx2.markers import finalize_slot_node

if TYPE_CHECKING:
    # Type-only: the hook's signature names the spine's own types, but importing
    # them at runtime would point session at its own consumers.
    from pyjinhx2.component import BaseComponent
    from pyjinhx2.segments import RenderedLevel

# The four pieces of per-request mutable state. They live here rather than beside
# their eventual consumers because the import rule runs one way only: reactive/
# imports session, never the reverse. Each defaults to None so that reading one
# outside a request is a miss, not a LookupError.
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


class NoActiveRequestScope(RuntimeError):
    """Raised when per-request state is touched outside an active request_scope()."""


class RenderSession:
    """Session providing Jinja environment with autoescape enabled."""

    def __init__(self, template_dir: str = "templates"):
        """Initialize render session.

        Args:
            template_dir: Directory to load templates from (default: "templates").
        """
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
            # Interpolating a component-valued slot must not stringify it; the
            # hook swaps in a placeholder the render pipeline resolves later.
            finalize=finalize_slot_node,
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


def get_cache_store() -> dict[object, object]:
    """Return this request's load cache store, or an empty dict outside a scope."""
    store = _cache_store.get()
    if store is None:
        return {}
    return store


@contextmanager
def request_scope(
    template_dir: str = "templates", session: "RenderSession | None" = None
) -> Iterator[RenderSession]:
    """Bind fresh per-request state for the duration of the block.

    Args:
        template_dir: Directory a newly-constructed RenderSession loads
            templates from. Ignored when ``session`` is given.
        session: An existing RenderSession to bind as this scope's current
            session, instead of constructing a fresh one. Lets a caller wire
            hooks (e.g. ``on_rendered``) onto a session before it becomes the
            one ``current_session()`` sees as active.

    Yields:
        The RenderSession bound for this scope.
    """
    if session is None:
        session = RenderSession(template_dir)
    session_token = _render_session.set(session)
    instances_token = _instances.set({})
    dirtied_token = _dirtied.set(set())
    cache_token = _cache_store.set({})
    try:
        yield session
    finally:
        # Reset by token rather than assigning None: a nested scope must hand the
        # outer scope its own state back, not clear the variable outright.
        _cache_store.reset(cache_token)
        _dirtied.reset(dirtied_token)
        _instances.reset(instances_token)
        _render_session.reset(session_token)
