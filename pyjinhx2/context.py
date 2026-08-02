"""PjxContext: the request-scoped, read-only handle onto session and reactive state.

This is deliberately narrower than v0.x's PjxContext: no user-data injection,
no load()-parameter introspection, no mutation methods. It is a view over
state that already lives in session.py's ContextVars and on request.state —
constructed on demand, never itself ContextVar-bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyjinhx2.session import (
    NoActiveRequestScope,
    RenderSession,
    current_session,
    get_cache_reverse,
    get_cache_store,
    get_dirtied,
    get_instances,
)

if TYPE_CHECKING:
    from starlette.requests import Request


@dataclass(frozen=True)
class PjxContext:
    """A live view of one request's pyjinhx state.

    Exposes the session bound by ``request_scope()``, the dirtied reactive
    keys, the instance registry, the two load-cache stores, the pjx header
    manifests parsed onto ``request.state``, and whatever an app's
    ``context_factory`` returned. Read-only: dirtying and mutation stay with
    ``reactive.mutations``.
    """

    # A facade, not a holder: every accessor re-reads session.py's ContextVars
    # on each call, so a PjxContext handed to a template cannot go stale and
    # cannot become a second, competing source of per-request truth. It binds
    # no ContextVar of its own for the same reason.

    request: Request | None

    @classmethod
    def current(cls) -> PjxContext:
        """Build a view over the request bound to the active scope.

        Raises:
            NoActiveRequestScope: If called outside an active ``request_scope()``.
        """
        session = current_session()
        if session is None:
            raise NoActiveRequestScope(
                "PjxContext.current() requires an active request_scope()"
            )
        return cls(request=getattr(session, "pjx_request", None))

    @property
    def session(self) -> RenderSession | None:
        """The RenderSession bound to this request, or None outside a scope."""
        return current_session()

    @property
    def dirtied(self) -> set[str]:
        """This request's dirtied reactive keys."""
        return get_dirtied()

    @property
    def instances(self) -> dict[str, object]:
        """This request's instance registry."""
        return get_instances()

    @property
    def cache_store(self) -> dict[object, object]:
        """This request's load cache store."""
        return get_cache_store()

    @property
    def cache_reverse(self) -> dict[str, set[tuple[type, object]]]:
        """This request's reactive-key -> cache-entry index."""
        return get_cache_reverse()

    def _state(self, name: str) -> Any:
        """The named ``request.state`` attribute, or None when unset."""
        if self.request is None:
            return None
        return getattr(self.request.state, name, None)
