"""RenderSession, the per-request ContextVars, and the request_scope that owns them."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader

from pyjinhx2.markers import finalize_slot_node

if TYPE_CHECKING:
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
        # Asset paths accumulate here as on_rendered fires bottom-up; a set because
        # the same component class contributes the same paths on every occurrence.
        self.asset_paths: set[str] = set()
        # Callbacks fired once per component render, after that level's
        # RenderedLevel is built (depth-first post-order once nested renders
        # exist). Subscribers read the finished descriptor/level; they never
        # trigger a second render.
        self.on_rendered: list[Callable[[Any, RenderedLevel], None]] = []


def current_session() -> RenderSession | None:
    """Return the RenderSession bound to this request, or None outside a scope."""
    return _render_session.get()


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
def request_scope(template_dir: str = "templates") -> Iterator[RenderSession]:
    """Bind fresh per-request state for the duration of the block.

    Args:
        template_dir: Directory the new RenderSession loads templates from.

    Yields:
        The RenderSession bound for this scope.
    """
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
