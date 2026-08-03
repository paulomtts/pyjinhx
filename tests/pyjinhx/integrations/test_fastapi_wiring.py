"""The FastAPI adapter: request scope, header parsing, T1/T2 response adaptation."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from pyjinhx.component import BaseComponent
from pyjinhx.config import PjxSettings
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.integrations.fastapi import apply_setup
from pyjinhx.reactive.response import ReactiveResponse


class Greeting(BaseComponent):
    name: str = "world"


Greeting.__pjx_descriptor__ = ClassDescriptor(
    template_path=Path("pjx_integrations_greeting.html"),
    slot_fields=frozenset(),
    children_field=None,
    css_paths=(),
    js_paths=(),
    strict=True,
    provenance={"template": Greeting},
)


def test_apply_setup_is_importable():
    assert callable(apply_setup)


def _settings(**kwargs) -> PjxSettings:
    return PjxSettings(**kwargs)


def test_apply_setup_registers_the_scope_middleware():
    app = FastAPI()
    apply_setup(app, _settings())
    assert any(
        middleware.cls.__name__  # pyright: ignore[reportAttributeAccessIssue]
        == "PjxScopeMiddleware"
        for middleware in app.user_middleware
    )


def test_apply_setup_is_idempotent():
    app = FastAPI()
    apply_setup(app, _settings())
    apply_setup(app, _settings())
    names = [
        m.cls.__name__  # pyright: ignore[reportAttributeAccessIssue]
        for m in app.user_middleware
    ]
    assert names.count("PjxScopeMiddleware") == 1


def test_static_files_are_mounted_when_static_root_is_set(tmp_path: Path):
    app = FastAPI()
    apply_setup(app, _settings(static_root=tmp_path))
    assert any(getattr(route, "name", None) == "static" for route in app.routes)


def test_no_static_mount_without_static_root():
    app = FastAPI()
    apply_setup(app, _settings())
    assert not any(getattr(route, "name", None) == "static" for route in app.routes)


def test_lifespan_configures_and_shuts_down_around_no_prior_lifespan():
    from pyjinhx.config import current_settings

    app = FastAPI()
    settings = _settings(inject_htmx=False)
    apply_setup(app, settings)
    with TestClient(app):
        assert current_settings().inject_htmx is False
    assert current_settings().inject_htmx is True


def test_lifespan_wraps_an_app_provided_lifespan():
    from contextlib import asynccontextmanager as _acm

    from pyjinhx.config import current_settings

    seen: list[bool] = []

    @_acm
    async def app_lifespan(_app):
        seen.append(current_settings().inject_htmx)
        yield

    app = FastAPI(lifespan=app_lifespan)
    apply_setup(app, _settings(inject_htmx=False))
    with TestClient(app):
        pass
    assert seen == [False]


def test_scope_is_entered_per_request_and_reset_after():
    from pyjinhx.session import current_session

    app = FastAPI()
    apply_setup(app, _settings())
    seen: list[object] = []

    @app.get("/ping")
    def ping():
        seen.append(current_session())
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/ping").json() == {"ok": True}
        assert client.get("/ping").json() == {"ok": True}

    assert len(seen) == 2
    assert all(session is not None for session in seen)
    assert seen[0] is not seen[1]
    assert current_session() is None


def test_scope_exits_when_the_handler_raises():
    from pyjinhx.session import current_session

    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/boom")
    def boom():
        raise RuntimeError("handler exploded")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/boom").status_code == 500
    assert current_session() is None


def test_manifests_are_parsed_onto_request_state():
    app = FastAPI()
    apply_setup(app, _settings())
    captured: dict[str, object] = {}

    @app.get("/state")
    def state(request: Request):
        captured["mounted"] = request.state.pjx_mounted
        captured["assets"] = request.state.pjx_assets
        captured["trigger"] = request.state.pjx_trigger
        return {"ok": True}

    with TestClient(app) as client:
        client.get(
            "/state",
            headers={
                "X-PJX-Mounted": '[{"id": "a", "type": "Card", "load": {}, "hash": "h"}]',
                "X-PJX-Assets": '["tok"]',
                "X-PJX-Trigger": '{"id": "a"}',
            },
        )

    assert captured["mounted"] == [{"id": "a", "type": "Card", "load": {}, "hash": "h"}]
    assert captured["assets"] == frozenset({"tok"})
    assert captured["trigger"] == {"id": "a"}


def test_cold_render_returns_html_with_the_runtime_inlined():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/page")
    def page():
        return Greeting(name="ada")

    with TestClient(app) as client:
        response = client.get("/page")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "hello ada" in response.text
    assert response.text.count("<script>") >= 1
    assert "pjx" in response.text


def test_mounted_request_does_not_reinject_the_runtime():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/page")
    def page():
        return Greeting(name="ada")

    with TestClient(app) as client:
        response = client.get("/page", headers={"X-PJX-Mounted": "[]"})

    assert "hello ada" in response.text
    assert "htmx" not in response.text


def test_mounted_request_is_honoured_without_a_request_parameter():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/page")
    def page():
        return Greeting(name="ada")

    with TestClient(app) as client:
        assert "htmx" not in client.get("/page", headers={"X-PJX-Mounted": "[]"}).text


def test_reactive_response_body_and_headers_reach_the_client():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/act")
    def act():
        return ReactiveResponse(primary="", mounted=[], redirect="/next")

    with TestClient(app) as client:
        response = client.post("/act", headers={"X-PJX-Mounted": "[]"})

    assert response.headers["HX-Reswap"] == "none"
    assert response.headers["HX-Redirect"] == "/next"
    assert "htmx" not in response.text


def test_reactive_response_never_reinjects_the_runtime():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/act")
    def act():
        return ReactiveResponse(primary="<p>ok</p>", mounted=[])

    with TestClient(app) as client:
        response = client.post("/act")

    assert response.text == "<p>ok</p>"
    assert "<script>" not in response.text


def test_non_pjx_returns_pass_through_untouched():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/json")
    def as_json():
        return {"ok": True}

    @app.get("/plain")
    def as_response():
        return PlainTextResponse("raw")

    with TestClient(app) as client:
        assert client.get("/json").json() == {"ok": True}
        plain = client.get("/plain")
        assert plain.text == "raw"
        assert plain.headers["content-type"].startswith("text/plain")
