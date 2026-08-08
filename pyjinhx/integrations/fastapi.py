"""The FastAPI/Starlette adapter: request scope, pjx headers, T1/T2 responses."""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, Response

from pyjinhx._component import BaseComponent
from pyjinhx.client.inject import (
    LoadedAssets,
    MountedManifest,
    TriggerManifest,
    inject_runtime,
)
from pyjinhx.config import (
    PjxSettings,
    configure_pyjinhx,
    current_settings,
    shutdown_pyjinhx,
)
from pyjinhx.integrations.base import (
    SETUP_FLAG,
    ContextFactory,
    register_backend,
)
from pyjinhx.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx.registry import register_rendered_instance
from pyjinhx.responses import PASSTHROUGH, PjxResponse, compose
from pyjinhx.session import (
    RenderSession,
    _environment_for,
    accumulate_assets,
    current_session,
    request_scope,
)

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = logging.getLogger("pyjinhx")


class FastAPIBackend:
    """The FastAPI adapter's Protocol surface: install flag, lifecycle, static, responses.

    It holds the settings because ``on_startup`` takes only the app: chaining a
    lifespan is where configure runs, and the settings resolved by ``setup()``
    have to reach that call somehow.
    """

    def __init__(
        self,
        settings: PjxSettings | None = None,
        *,
        context_factory: ContextFactory | None = None,
    ) -> None:
        self.settings = settings if settings is not None else PjxSettings()
        self.context_factory = context_factory

    def accepts(self, app: object) -> bool:
        """Whether ``app`` is an application this adapter can wire into.

        Duck-typed rather than isinstance-checked so a caller passing a plain
        Starlette app, a sub-application or a test double is not rejected for
        the sake of a type name.
        """
        return hasattr(app, "add_middleware") and hasattr(app, "router")

    def is_installed(self, app: object) -> bool:
        return bool(getattr(getattr(app, "state", None), SETUP_FLAG, False))

    def mark_installed(self, app: object) -> None:
        setattr(app.state, SETUP_FLAG, True)  # pyright: ignore[reportAttributeAccessIssue]

    def mount_static(self, app: object, directory: str) -> None:
        from starlette.staticfiles import StaticFiles

        app.mount(  # pyright: ignore[reportAttributeAccessIssue]
            "/static", StaticFiles(directory=directory), name="static"
        )

    def on_startup(self, app: object) -> None:
        configure_pyjinhx(self.settings)

    def on_shutdown(self, app: object) -> None:
        shutdown_pyjinhx()

    def to_response(
        self, result: object, request: object | None, response: Any = None
    ) -> object:
        """Emit compose()'s answer, or hand back a result that is not pjx's.

        Composition — including whether this request fans out — is decided by
        `pyjinhx.responses.compose`, which no framework has to be installed for.
        All that is left here is turning that answer into a Starlette response.
        """
        session = current_session()
        # Always set: to_response only runs from inside PjxScopeMiddleware's
        # request_scope(), which is the sole entry point for a pjx endpoint.
        assert session is not None, "handler return outside a request_scope()"
        # Before compose(), because compose() is what renders the component and
        # the runtime has to be in the session by then. Only a component return
        # can be a cold page render; every other shape is a fragment.
        if isinstance(result, BaseComponent):
            inject_runtime(session, request or getattr(session, "pjx_request", None))
        composed = compose(result, session=session)
        if composed is PASSTHROUGH:
            return _translate_native_redirect(
                result, request or getattr(session, "pjx_request", None)
            )
        assert isinstance(composed, PjxResponse)
        headers, status = _merge_injected(composed, response)
        return HTMLResponse(composed.body, headers=headers, status_code=status)

    def chain_lifespan(self, app: Starlette) -> None:
        """Run the startup/shutdown hooks around whatever lifespan app has.

        Chaining is spelled per framework, which is why the Protocol fixes only
        the two call points and leaves this out of the interface.
        """
        original = app.router.lifespan_context

        @asynccontextmanager
        async def pyjinhx_lifespan(app_instance: object):
            self.on_startup(app_instance)
            try:
                if original is not None:
                    async with original(app_instance) as state:
                        yield state
                else:
                    yield
            finally:
                self.on_shutdown(app_instance)

        app.router.lifespan_context = pyjinhx_lifespan  # pyright: ignore[reportAttributeAccessIssue]


def apply_setup(
    app: Starlette,
    settings: PjxSettings,
    *,
    context_factory: Callable[[Any], object | None] | None = None,
) -> None:
    """Wire pyjinhx into ``app``: lifespan, request scope, static files, routes.

    Applying setup a second time to the same app is a no-op, so a re-entrant
    ``setup()`` cannot stack two scopes or two lifespans on one request.
    """
    backend = FastAPIBackend(settings, context_factory=context_factory)
    if backend.is_installed(app):
        logger.warning("pyjinhx setup already applied to this app; skipping")
        return
    backend.chain_lifespan(app)
    app.add_middleware(PjxScopeMiddleware, context_factory=context_factory)
    if settings.static_root is not None:
        backend.mount_static(app, str(settings.static_root))
    _install_route_adaptation(backend, app)
    backend.mark_installed(app)


_BACKEND = FastAPIBackend()
register_backend(_BACKEND)


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
        load_context = (
            self.context_factory(request) if self.context_factory is not None else None
        )
        # The `with` block, not a manual enter/exit: a handler exception must
        # still reset the ContextVars before it propagates. The endpoint
        # wrapper stashes the request on the session too, so inject_runtime()
        # can answer "is this mounted?" even when the handler's own signature
        # never declares a Request parameter.
        # The session is built here rather than defaulted inside request_scope():
        # the three render hooks below are exported unsubscribed, and this is
        # the one place production wiring attaches them before the scope opens.
        # request_scope() seeds a session it builds itself from the configured
        # settings, but it leaves a caller-supplied one alone — so the same
        # seeding has to happen here, at the only call site that supplies one.
        settings = current_settings()
        session = RenderSession(jinja_env=_environment_for(settings))
        session.on_rendered.append(accumulate_assets)
        session.on_rendered.append(stamp_reactive_root_attrs)
        session.on_rendered.append(register_rendered_instance)
        with request_scope(session=session, load_context=load_context) as session:
            session.pjx_request = request  # pyright: ignore[reportAttributeAccessIssue]
            session.pjx_mounted = MountedManifest.parse(request)
            session.pjx_assets = LoadedAssets.parse(request)
            session.pjx_trigger = TriggerManifest.parse(request)
            return await call_next(request)


def _request_from(kwargs: dict[str, Any]) -> Any:
    """The ``Request`` argument FastAPI injected, if the handler declared one."""
    from starlette.requests import Request

    for value in kwargs.values():
        if isinstance(value, Request):
            return value
    return None


def _response_from(kwargs: dict[str, Any]) -> Any:
    """The ``Response`` argument FastAPI injected, if the handler declared one."""
    from starlette.responses import Response as StarletteResponse

    for value in kwargs.values():
        if isinstance(value, StarletteResponse):
            return value
    return None


def _merge_injected(composed: PjxResponse, response: Any) -> tuple[dict[str, str], int]:
    """Fold what the handler set on its injected ``Response`` into the composed one.

    The injected object wins on collisions: setting a header there is an explicit
    act by the handler, while the composed headers are pyjinhx's own defaults.
    Starlette cannot say whether a status was assigned or left at its default, so
    only a non-200 counts as deliberate. ``content-length`` is dropped because it
    describes the injected object's empty body, not the composed one.
    """
    if response is None:
        return composed.headers, composed.status
    injected = {
        key: value
        for key, value in dict(response.headers).items()
        if key.lower() != "content-length"
    }
    status = getattr(response, "status_code", None)
    return (
        {**composed.headers, **injected},
        composed.status if status in (None, 200) else status,
    )


def _is_htmx(request: Any) -> bool:
    """Whether htmx, rather than the browser itself, issued this request."""
    if request is None:
        return False
    headers = getattr(request, "headers", None)
    if headers is None:
        return False
    return headers.get("HX-Request") == "true"


def _translate_native_redirect(result: object, request: Any) -> object:
    """Turn a native 3xx into the 204 + ``HX-Redirect`` htmx can actually follow.

    htmx follows a 3xx transparently inside XHR and swaps the redirect target's
    body into the triggering element, which is never what the handler meant. The
    check is duck-typed on shape, not on ``RedirectResponse``, so hand-built and
    third-party redirect responses translate too.
    """
    if not _is_htmx(request):
        return result
    status = getattr(result, "status_code", None)
    if status not in range(300, 400):
        return result
    headers = getattr(result, "headers", None)
    if headers is None:
        return result
    location = headers.get("Location") or headers.get("location")
    if not location:
        return result
    return Response(status_code=204, headers={"HX-Redirect": location})


def _adapt_endpoint(
    backend: FastAPIBackend, endpoint: Callable[..., Any]
) -> Callable[..., Any]:
    """Return a version of ``endpoint`` whose pjx returns become responses."""

    @functools.wraps(endpoint)
    async def adapted(*args: Any, **kwargs: Any) -> Any:
        result = endpoint(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return backend.to_response(
            result, _request_from(kwargs), _response_from(kwargs)
        )

    setattr(adapted, "__pjx_adapted__", True)  # noqa: B010
    return adapted


def _returns_pjx(endpoint: Callable[..., Any]) -> bool:
    """Whether ``endpoint``'s return annotation is a pyjinhx return type.

    FastAPI would otherwise infer a response_model from a component class and
    validate the component into JSON before the adapter ever sees it.
    """
    annotation = inspect.signature(endpoint).return_annotation
    return isinstance(annotation, type) and issubclass(annotation, BaseComponent)


def _install_route_adaptation(backend: FastAPIBackend, app: Starlette) -> None:
    """Adapt pjx returns for routes registered before and after setup().

    A handler annotated with a component class on a route declared before
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
            super().__init__(path, _adapt_endpoint(backend, endpoint), **kwargs)

    def patch_routes(routes: Iterable[Any]) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                call = route.dependant.call
                if call is not None and not getattr(call, "__pjx_adapted__", False):
                    adapted = _adapt_endpoint(backend, call)
                    route.dependant.call = adapted
                    # An included sub-router is dispatched through effective
                    # route contexts that fastapi rebuilds from ``endpoint``,
                    # not from the dependant we just patched.
                    route.endpoint = adapted
                    route.app = request_response(route.get_route_handler())
                continue
            # fastapi >= 0.137 keeps included routes under a sentinel route
            # instead of flattening them into app.router.routes.
            included = getattr(route, "original_router", None)
            if included is not None:
                patch_routes(included.routes)

    app_router: Any = app.router
    app_router.route_class = PjxRoute
    patch_routes(app_router.routes)

    # Routers included after setup never see PjxRoute: fastapi keeps the
    # sub-router's own APIRoute objects instead of rebuilding them with the
    # app's route_class, so adaptation has to happen at include time.
    include_router = app_router.include_router

    @functools.wraps(include_router)
    def adapting_include_router(router: Any, **kwargs: Any) -> Any:
        result = include_router(router, **kwargs)
        patch_routes(router.routes)
        return result

    app_router.include_router = adapting_include_router
