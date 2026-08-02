"""The FastAPI/Starlette adapter: request scope, pjx headers, T1/T2 responses."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware

from pyjinhx2.client.inject import LoadedAssets, MountedManifest, TriggerManifest
from pyjinhx2.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx2.session import request_scope

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = logging.getLogger("pyjinhx2")


def apply_setup(
    app: Starlette,
    settings: PjxSettings,
    *,
    context_factory: Callable[[Any], object | None] | None = None,
) -> None:
    """Wire pyjinhx2 into ``app``: lifespan, request scope, static files.

    Applying setup a second time to the same app is a no-op, so a re-entrant
    ``setup()`` cannot stack two scopes or two lifespans on one request.
    """
    if getattr(app.state, "pyjinhx_setup", False):
        logger.warning("pyjinhx2 setup already applied to this app; skipping")
        return
    _chain_lifespan(app, settings)
    app.add_middleware(PjxScopeMiddleware, context_factory=context_factory)
    if settings.static_root is not None:
        from starlette.staticfiles import StaticFiles

        app.mount("/static", StaticFiles(directory=settings.static_root), name="static")
    app.state.pyjinhx_setup = True


def _chain_lifespan(app: Starlette, settings: PjxSettings) -> None:
    """Run configure/shutdown around whatever lifespan the app already has."""
    original = app.router.lifespan_context

    @asynccontextmanager
    async def pyjinhx_lifespan(app_instance: object):
        configure_pyjinhx(settings)
        try:
            if original is not None:
                async with original(app_instance) as state:
                    yield state
            else:
                yield
        finally:
            shutdown_pyjinhx()

    app.router.lifespan_context = pyjinhx_lifespan  # pyright: ignore[reportAttributeAccessIssue]


class PjxScopeMiddleware(BaseHTTPMiddleware):
    """Binds one ``request_scope()`` per request and parses the pjx headers.

    The handler runs inside the scope, so ``current_session()`` and the dirtied
    keys a mutation records are the ones this request's response is built from.
    """

    def __init__(
        self,
        app: Any,
        *,
        context_factory: Callable[[Any], object | None] | None = None,
    ) -> None:
        super().__init__(app)
        self.context_factory = context_factory

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        request.state.pjx_mounted = MountedManifest.parse(request)
        request.state.pjx_assets = LoadedAssets.parse(request)
        request.state.pjx_trigger = TriggerManifest.parse(request)
        request.state.pjx_context = (
            self.context_factory(request) if self.context_factory is not None else None
        )
        # The `with` block, not a manual enter/exit: a handler exception must
        # still reset the ContextVars before it propagates. The endpoint
        # wrapper stashes the request on the session too, so inject_runtime()
        # can answer "is this mounted?" even when the handler's own signature
        # never declares a Request parameter.
        with request_scope() as session:
            session.pjx_request = request  # pyright: ignore[reportAttributeAccessIssue]
            return await call_next(request)
