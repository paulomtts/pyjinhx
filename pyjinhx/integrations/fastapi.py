from __future__ import annotations

import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from pyjinhx.client import ClientBackend
from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx.registry import Registry

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = logging.getLogger("pyjinhx")


class FastAPIClientBackend(ClientBackend):
    """
    Default client backend for FastAPI and Starlette.

    Wraps a request object's ``.headers`` mapping. The backend instance is also
    duck-typed for ``render()`` (``.headers.get``) without a separate proxy.
    """

    def __init__(self, request: object) -> None:
        headers = getattr(request, "headers", None)
        if headers is None:
            raise TypeError("FastAPIClientBackend requires request.headers")
        self.headers = headers

    def get_header(self, name: str) -> str | None:
        return self.headers.get(name)


def apply_setup(
    app: Starlette,
    settings: PjxSettings,
    *,
    context_factory: Callable[[Any], object | None] | None = None,
    static_root: str | os.PathLike[str] | None = None,
) -> None:
    if getattr(app.state, "pyjinhx_setup", False):
        logger.warning(
            "pyjinhx setup already applied to this app; skipping reconfiguration"
        )
        return
    _chain_lifespan(app, settings)
    app.add_middleware(_registry_middleware_class(context_factory))
    if static_root is not None:
        from starlette.staticfiles import StaticFiles

        app.mount("/static", StaticFiles(directory=static_root), name="static")
    app.state.pyjinhx_setup = True


def _chain_lifespan(app: Starlette, settings: PjxSettings) -> None:
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

    # Replace Starlette's internal lifespan with our chained one.
    app.router.lifespan_context = pyjinhx_lifespan  # type: ignore[assignment]


def _registry_middleware_class(
    context_factory: Callable[[Any], object | None] | None,
) -> type:
    from starlette.middleware.base import BaseHTTPMiddleware

    class RegistryScopeMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            load_context = (
                context_factory(request) if context_factory is not None else None
            )
            backend = FastAPIClientBackend(request)
            with Registry.request_scope(
                load_context=load_context,
                client_backend=backend,
            ):
                response = await call_next(request)
                backend.apply_response_directives(response)
                return response

    return RegistryScopeMiddleware
