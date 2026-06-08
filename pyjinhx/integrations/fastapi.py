from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from pyjinhx.core.registry import Registry
from pyjinhx.config import PyJinhxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx.reactive.backend import fastapi_client_backend

logger = logging.getLogger("pyjinhx")


def apply_setup(
    app: object,
    settings: PyJinhxSettings,
    *,
    load_context_factory: Callable[[Any], object | None] | None = None,
) -> None:
    if getattr(app.state, "pyjinhx_setup", False):
        logger.debug("pyjinhx setup already applied; skipping")
        return
    _chain_lifespan(app, settings)
    app.add_middleware(_registry_middleware_class(load_context_factory))
    app.state.pyjinhx_setup = True


def _chain_lifespan(app: object, settings: PyJinhxSettings) -> None:
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

    app.router.lifespan_context = pyjinhx_lifespan


def _registry_middleware_class(
    load_context_factory: Callable[[Any], object | None] | None,
) -> type:
    from starlette.middleware.base import BaseHTTPMiddleware

    factory = load_context_factory

    class RegistryScopeMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            load_context = factory(request) if factory is not None else None
            with Registry.request_scope(
                load_context=load_context,
                client_backend=fastapi_client_backend(request),
            ):
                return await call_next(request)

    return RegistryScopeMiddleware
