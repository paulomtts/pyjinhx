"""The FastAPI/Starlette adapter: request scope, pjx headers, T1/T2 responses."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from pyjinhx2.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx

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


class PjxScopeMiddleware:
    def __init__(self, app: Any, *, context_factory: Any = None) -> None:
        raise NotImplementedError
