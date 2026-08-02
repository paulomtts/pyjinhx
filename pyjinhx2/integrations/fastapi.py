"""The FastAPI/Starlette adapter: request scope, pjx headers, T1/T2 responses."""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse

from pyjinhx2.client.inject import (
    LoadedAssets,
    MountedManifest,
    TriggerManifest,
    inject_runtime,
)
from pyjinhx2.component import BaseComponent
from pyjinhx2.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx2.reactive.response import ReactiveResponse
from pyjinhx2.render import render
from pyjinhx2.session import current_session, request_scope

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
    _install_route_adaptation(app)
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


def _to_response(result: object, request: Any) -> object:
    """Adapt a pjx handler return into an HTML response, or pass it through.

    A ReactiveResponse already carries its composed body and htmx headers (T2);
    a bare component is this request's primary render, so the runtime is offered
    to it and inlined only when the request is not already mounted (T1).
    """
    if isinstance(result, ReactiveResponse):
        return HTMLResponse(str(result.body), headers=result.headers)
    if isinstance(result, BaseComponent):
        session = current_session()
        # Always set: _to_response only runs from inside PjxScopeMiddleware's
        # request_scope(), which is the sole entry point for a pjx endpoint.
        assert session is not None, "component return outside a request_scope()"
        inject_runtime(session, request or getattr(session, "pjx_request", None))
        return HTMLResponse(render(result, session=session))
    return result


def _request_from(kwargs: dict[str, Any]) -> Any:
    """The ``Request`` argument FastAPI injected, if the handler declared one."""
    from starlette.requests import Request

    for value in kwargs.values():
        if isinstance(value, Request):
            return value
    return None


def _adapt_endpoint(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    """Return a version of ``endpoint`` whose pjx returns become responses."""

    @functools.wraps(endpoint)
    async def adapted(*args: Any, **kwargs: Any) -> Any:
        result = endpoint(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return _to_response(result, _request_from(kwargs))

    return adapted


def _returns_pjx(endpoint: Callable[..., Any]) -> bool:
    """Whether ``endpoint``'s return annotation is a pyjinhx2 return type.

    FastAPI would otherwise infer a response_model from a component class and
    validate the component into JSON before the adapter ever sees it.
    """
    annotation = inspect.signature(endpoint).return_annotation
    return isinstance(annotation, type) and issubclass(
        annotation, (BaseComponent, ReactiveResponse)
    )


def _install_route_adaptation(app: Starlette) -> None:
    """Adapt pjx returns for routes registered before and after setup().

    A handler annotated ``-> ReactiveResponse`` on a route declared before
    ``apply_setup()`` cannot be patched: FastAPI resolves that annotation into
    a pydantic response_model inside ``APIRoute.__init__``, before this
    function ever runs. Omit the return annotation, or annotate with a real
    BaseComponent/pydantic subclass, on routes declared ahead of setup.
    """
    from fastapi.routing import APIRoute
    from starlette.routing import request_response

    class PjxRoute(APIRoute):
        def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any):
            if _returns_pjx(endpoint):
                kwargs["response_model"] = None
            super().__init__(path, _adapt_endpoint(endpoint), **kwargs)

    app.router.route_class = PjxRoute  # pyright: ignore[reportAttributeAccessIssue]
    for route in app.router.routes:
        if isinstance(route, APIRoute) and route.dependant.call is not None:
            route.dependant.call = _adapt_endpoint(route.dependant.call)
            route.app = request_response(route.get_route_handler())
