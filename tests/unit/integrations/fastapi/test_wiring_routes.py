"""Tests for the FastAPI integration's router adaptation, injected responses and runtime and theme injection."""

from typing import TYPE_CHECKING, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import (
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)

from pyjinhx.integrations.fastapi import apply_setup
from pyjinhx.rendering.session import request_scope
from tests.unit.integrations.fastapi._wiring_helpers import Greeting, _settings

if TYPE_CHECKING:
    from starlette.routing import BaseRoute


class _FakeRouter:
    """Stands in for the ``.original_router`` of fastapi's _IncludedRouter."""

    def __init__(self, routes):
        self.routes = routes


class _FakeIncludedRoute:
    """Duck-typed stand-in for fastapi>=0.137's routing._IncludedRouter."""

    def __init__(self, routes):
        self.original_router = _FakeRouter(routes)


def _real_api_route(path: str = "/deep"):
    from fastapi.routing import APIRoute

    def handler() -> str:
        return "hello"

    return APIRoute(path, handler)


def test_included_router_routes_are_adapted_one_level_deep():
    app = FastAPI()
    inner = _real_api_route()
    original_call = inner.dependant.call
    app.router.routes.append(cast("BaseRoute", _FakeIncludedRoute([inner])))

    apply_setup(app, _settings())

    assert inner.dependant.call is not original_call


def test_included_router_routes_are_adapted_two_levels_deep():
    app = FastAPI()
    inner = _real_api_route("/deeper")
    original_call = inner.dependant.call
    app.router.routes.append(
        cast("BaseRoute", _FakeIncludedRoute([_FakeIncludedRoute([inner])]))
    )

    apply_setup(app, _settings())

    assert inner.dependant.call is not original_call


def test_nested_route_without_a_dependant_call_is_left_alone():
    app = FastAPI()
    inner = _real_api_route("/unguarded")
    inner.dependant.call = None
    app.router.routes.append(cast("BaseRoute", _FakeIncludedRoute([inner])))

    apply_setup(app, _settings())

    assert inner.dependant.call is None


def test_unknown_route_shapes_in_the_tree_are_skipped():
    from starlette.routing import Route, WebSocketRoute

    async def endpoint(websocket):  # pragma: no cover - never called
        raise AssertionError

    app = FastAPI()
    inner = _real_api_route("/mixed")
    original_call = inner.dependant.call
    app.router.routes.append(
        cast(
            "BaseRoute",
            _FakeIncludedRoute(
                [
                    Route("/plain", lambda request: PlainTextResponse("x")),
                    WebSocketRoute("/ws", endpoint),
                    _FakeIncludedRoute([]),
                    inner,
                ]
            ),
        )
    )

    apply_setup(app, _settings())

    assert inner.dependant.call is not original_call


def test_include_router_after_setup_is_adapted():
    from fastapi import APIRouter

    app = FastAPI()
    apply_setup(app, _settings())

    sub = APIRouter()

    @sub.get("/sub-after")
    def sub_after() -> Greeting:
        return Greeting(name="after")

    app.include_router(sub)

    with TestClient(app) as client:
        response = client.get("/sub-after")

    assert response.status_code == 200
    # Asserting on the rendered fragment, not just the name: an unadapted route
    # also answers 200 with the name in it, as pydantic-serialized JSON.
    assert response.headers["content-type"].startswith("text/html")
    assert "<div>hello after</div>" in response.text


def test_include_router_before_setup_is_adapted():
    from fastapi import APIRouter

    app = FastAPI()
    sub = APIRouter()

    @sub.get("/sub-before")
    def sub_before():
        return Greeting(name="before")

    app.include_router(sub)
    apply_setup(app, _settings())

    with TestClient(app) as client:
        response = client.get("/sub-before")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<div>hello before</div>" in response.text


def test_nested_include_router_is_adapted_end_to_end():
    from fastapi import APIRouter

    app = FastAPI()
    apply_setup(app, _settings())

    inner = APIRouter()

    @inner.get("/nested-deep")
    def nested_deep() -> Greeting:
        return Greeting(name="deep")

    outer = APIRouter()
    outer.include_router(inner)
    app.include_router(outer)

    with TestClient(app) as client:
        response = client.get("/nested-deep")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<div>hello deep</div>" in response.text


def test_response_from_finds_the_injected_response():
    from pyjinhx.integrations.fastapi import _response_from

    injected = Response()
    assert _response_from({"x": 1, "response": injected}) is injected


def test_response_from_returns_none_without_an_injected_response():
    from pyjinhx.integrations.fastapi import _response_from

    assert _response_from({"x": 1, "name": "world"}) is None


def test_to_response_merges_injected_headers_and_non_default_status():
    from pyjinhx.integrations.fastapi import FastAPIBackend

    backend = FastAPIBackend(_settings())
    injected = Response()
    injected.headers["X-Custom"] = "yes"
    injected.status_code = 201
    with request_scope():
        adapted = cast(
            HTMLResponse,
            backend.to_response("<div>hi</div>", None, injected),
        )
    assert adapted.status_code == 201
    assert adapted.headers["X-Custom"] == "yes"
    assert adapted.body == b"<div>hi</div>"


def test_to_response_leaves_status_alone_when_injected_response_is_untouched():
    from pyjinhx.integrations.fastapi import FastAPIBackend

    backend = FastAPIBackend(_settings())
    with request_scope():
        untouched = cast(
            HTMLResponse,
            backend.to_response("<div>hi</div>", None, Response()),
        )
        baseline = cast(
            HTMLResponse,
            backend.to_response("<div>hi</div>", None),
        )
    assert untouched.status_code == baseline.status_code == 200
    assert untouched.body == baseline.body == b"<div>hi</div>"
    assert untouched.headers["content-length"] == baseline.headers["content-length"]


def test_injected_response_headers_and_status_reach_the_client():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/hello")
    def hello(response: Response) -> Greeting:
        response.headers["X-Custom"] = "yes"
        response.status_code = 201
        return Greeting(name="ana")

    with TestClient(app) as client:
        result = client.get("/hello")

    assert result.status_code == 201
    assert result.headers["X-Custom"] == "yes"
    assert "ana" in result.text


def test_untouched_injected_response_changes_nothing_for_the_client():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/with")
    def with_response(response: Response) -> Greeting:
        return Greeting(name="ana")

    @app.get("/without")
    def without_response() -> Greeting:
        return Greeting(name="ana")

    with TestClient(app) as client:
        injected = client.get("/with")
        plain = client.get("/without")

    assert injected.status_code == plain.status_code == 200
    assert injected.text == plain.text


def test_native_redirect_still_translates_with_an_injected_response():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/go")
    def go(response: Response):
        response.headers["X-Custom"] = "yes"
        response.status_code = 201
        return RedirectResponse(url="/next", status_code=303)

    with TestClient(app) as client:
        result = client.post(
            "/go", headers={"HX-Request": "true"}, follow_redirects=False
        )

    assert result.status_code == 204
    assert result.headers["HX-Redirect"] == "/next"
    assert "X-Custom" not in result.headers


def test_direct_render_return_still_injects_the_runtime():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/page")
    def page():
        return Greeting(name="ada").render()

    with TestClient(app) as client:
        response = client.get("/page")

    assert "ada" in response.text
    assert "<script>" in response.text


def test_direct_render_return_injects_the_runtime_exactly_once():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/page")
    def page():
        component = Greeting(name="ada")
        component.render()
        return component.render()

    with TestClient(app) as client:
        response = client.get("/page")

    assert response.text.count('id="pjx-style"') == 1


def test_object_return_still_injects_the_runtime_exactly_once():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/page")
    def page():
        return Greeting(name="ada")

    with TestClient(app) as client:
        response = client.get("/page")

    assert "<script>" in response.text
    assert response.text.count('id="pjx-style"') == 1


def test_mounted_request_direct_render_gets_no_runtime():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/frag")
    def frag():
        return Greeting(name="ada").render()

    with TestClient(app) as client:
        response = client.get("/frag", headers={"X-PJX-Mounted": "[]"})

    assert "ada" in response.text
    assert "<script>" not in response.text


def test_fastapi_object_return_emits_the_theme_once_and_first():
    app = FastAPI()
    apply_setup(app, _settings(theme="default"))

    @app.get("/page")
    def page():
        return Greeting(name="ada")

    with TestClient(app) as client:
        response = client.get("/page")

    text = response.text
    assert text.count('<style id="pjx-theme">') == 1
    theme_at = text.index('<style id="pjx-theme">')
    assert theme_at == text.index("<style")
    assert theme_at < text.index('id="pjx-style"')


def test_fastapi_double_direct_render_emits_the_theme_once():
    app = FastAPI()
    apply_setup(app, _settings(theme="default"))

    @app.get("/page")
    def page():
        component = Greeting(name="ada")
        component.render()
        return component.render()

    with TestClient(app) as client:
        response = client.get("/page")

    assert response.text.count('<style id="pjx-theme">') == 1


def test_fastapi_mounted_request_gets_no_theme():
    app = FastAPI()
    apply_setup(app, _settings(theme="default"))

    @app.get("/page")
    def page():
        return Greeting(name="ada")

    with TestClient(app) as client:
        response = client.get("/page", headers={"X-PJX-Mounted": "[]"})

    assert "ada" in response.text
    assert "pjx-theme" not in response.text
