"""The FastAPI adapter: request scope, header parsing, T1/T2 response adaptation."""

from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)

from pyjinhx._component import BaseComponent
from pyjinhx.config import PjxSettings
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.integrations.fastapi import apply_setup
from pyjinhx.session import request_scope


class Greeting(BaseComponent):
    name: str = "world"


Greeting.__pjx_descriptor__ = ClassDescriptor(
    template_path=Path(__file__).parent.parent.parent
    / "templates"
    / "pjx_integrations_greeting.html",
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


def test_manifests_are_parsed_onto_the_session():
    app = FastAPI()
    apply_setup(app, _settings())
    captured: dict[str, object] = {}

    @app.get("/state")
    def state(request: Request):
        from pyjinhx.session import current_session

        session = current_session()
        assert session is not None
        captured["mounted"] = session.pjx_mounted
        captured["assets"] = session.pjx_assets
        captured["trigger"] = session.pjx_trigger
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


def test_native_redirect_becomes_the_htmx_redirect_header():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/act")
    def act():
        return RedirectResponse("/next", status_code=303)

    with TestClient(app) as client:
        response = client.post(
            "/act",
            headers={"X-PJX-Mounted": "[]", "HX-Request": "true"},
        )

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/next"
    assert "htmx" not in response.text


def test_string_return_never_reinjects_the_runtime():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/act")
    def act():
        return "<p>ok</p>"

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


def test_backend_satisfies_the_integration_protocol():
    from pyjinhx.integrations.base import IntegrationBackend
    from pyjinhx.integrations.fastapi import FastAPIBackend

    assert isinstance(FastAPIBackend(_settings()), IntegrationBackend)


def test_backend_install_flag_uses_the_shared_setup_flag_name():
    from pyjinhx.integrations.base import SETUP_FLAG
    from pyjinhx.integrations.fastapi import FastAPIBackend

    app = FastAPI()
    backend = FastAPIBackend(_settings())
    assert backend.is_installed(app) is False
    backend.mark_installed(app)
    assert getattr(app.state, SETUP_FLAG) is True
    assert backend.is_installed(app) is True


def test_backend_mount_static_serves_the_directory(tmp_path: Path):
    from pyjinhx.integrations.fastapi import FastAPIBackend

    (tmp_path / "app.css").write_text("body{}", encoding="utf-8")
    app = FastAPI()
    FastAPIBackend(_settings()).mount_static(app, str(tmp_path))
    with TestClient(app) as client:
        assert client.get("/static/app.css").status_code == 200


def test_backend_startup_and_shutdown_move_the_process_settings(tmp_path: Path):
    from pyjinhx.config import current_settings
    from pyjinhx.integrations.fastapi import FastAPIBackend

    app = FastAPI()
    backend = FastAPIBackend(_settings(static_root=str(tmp_path)))
    backend.on_startup(app)
    assert current_settings().static_root == str(tmp_path)
    backend.on_shutdown(app)
    assert current_settings().static_root is None


def test_backend_to_response_composes_pjx_returns_and_passes_others_through():
    from pyjinhx.integrations.fastapi import FastAPIBackend

    backend = FastAPIBackend(_settings())
    # to_response asserts an active RenderSession (it is only ever called from
    # inside PjxScopeMiddleware's request_scope()), so this unit test binds one
    # by hand rather than going through a live request.
    with request_scope():
        adapted = cast(
            HTMLResponse,
            backend.to_response("<div>hi</div>", None),
        )
        assert adapted.status_code == 200
        assert adapted.body == b"<div>hi</div>"
        assert backend.to_response({"json": True}, None) == {"json": True}


def test_scope_session_resolves_an_absolute_template_path(tmp_path: Path):
    """A descriptor's template_path is always absolute; the request session must find it."""
    template = tmp_path / "abs_greeting.pjx"
    template.write_text("<p>hi {{ name }}</p>")

    class AbsGreeting(BaseComponent):
        name: str = "world"

    AbsGreeting.__pjx_descriptor__ = ClassDescriptor(
        template_path=template,
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": AbsGreeting},
    )

    app = FastAPI()
    apply_setup(app, _settings(inject_htmx=False))

    @app.get("/abs")
    def abs_route():
        return AbsGreeting(name="pjx")

    with TestClient(app) as client:
        response = client.get("/abs")

    assert response.status_code == 200
    assert "<p>hi pjx</p>" in response.text


def test_scope_session_stamps_reactive_roots_and_inlines_css(tmp_path: Path):
    """The request session carries the on_rendered hooks a reactive page needs."""
    from pyjinhx.reactive.component import ReactiveComponent

    (tmp_path / "abs_badge.pjx").write_text("<b>{{ label }}</b>")
    (tmp_path / "abs_badge.css").write_text("b { color: rebeccapurple }")

    class AbsBadge(ReactiveComponent):
        label: str = "x"

    AbsBadge.__pjx_descriptor__ = ClassDescriptor(
        template_path=tmp_path / "abs_badge.pjx",
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(tmp_path / "abs_badge.css",),
        js_paths=(),
        strict=True,
        provenance={"template": AbsBadge},
    )

    app = FastAPI()
    apply_setup(app, _settings(inject_htmx=False))

    @app.get("/badge")
    def badge_route():
        return AbsBadge(id="badge", label="hi")

    with TestClient(app) as client:
        response = client.get("/badge")

    assert 'data-pjx-id="badge"' in response.text
    assert "rebeccapurple" in response.text


def test_registering_the_module_publishes_a_backend():
    import pyjinhx.integrations.fastapi  # noqa: F401
    from pyjinhx.integrations.base import IntegrationBackend, get_backend

    assert isinstance(get_backend(), IntegrationBackend)


def test_htmx_native_redirect_becomes_hx_redirect():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/go")
    def go():
        return RedirectResponse(url="/next", status_code=303)

    with TestClient(app) as client:
        response = client.post(
            "/go", headers={"HX-Request": "true"}, follow_redirects=False
        )

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/next"
    assert response.text == ""


def test_non_htmx_native_redirect_is_untouched():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/go")
    def go():
        return RedirectResponse(url="/next", status_code=303)

    with TestClient(app) as client:
        response = client.post("/go", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/next"
    assert "HX-Redirect" not in response.headers


def test_hand_built_redirect_response_translates_too():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/raw")
    def raw():
        return Response(status_code=302, headers={"location": "/x"})

    with TestClient(app) as client:
        response = client.post(
            "/raw", headers={"HX-Request": "true"}, follow_redirects=False
        )

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/x"


def test_translate_native_redirect_handles_case_sensitive_headers():
    from types import SimpleNamespace

    from pyjinhx.integrations.fastapi import _translate_native_redirect

    request = SimpleNamespace(headers={"HX-Request": "true"})
    result = SimpleNamespace(status_code=307, headers={"Location": "/cap"})

    translated = _translate_native_redirect(result, request)

    assert translated.status_code == 204  # pyright: ignore[reportAttributeAccessIssue]
    assert translated.headers["HX-Redirect"] == "/cap"  # pyright: ignore[reportAttributeAccessIssue]


def test_translate_native_redirect_handles_lowercase_only_third_party_headers():
    from types import SimpleNamespace

    from pyjinhx.integrations.fastapi import _translate_native_redirect

    request = SimpleNamespace(headers={"HX-Request": "true"})
    result = SimpleNamespace(status_code=307, headers={"location": "/low"})

    translated = _translate_native_redirect(result, request)

    assert translated.headers["HX-Redirect"] == "/low"  # pyright: ignore[reportAttributeAccessIssue]


def test_htmx_non_redirect_response_is_untouched():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.get("/data")
    def data():
        return JSONResponse({"ok": True})

    with TestClient(app) as client:
        response = client.get("/data", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "HX-Redirect" not in response.headers


def test_hx_location_response_is_not_reinterpreted():
    app = FastAPI()
    apply_setup(app, _settings())

    @app.post("/client-nav")
    def client_nav():
        return Response(status_code=204, headers={"HX-Location": "/y"})

    with TestClient(app) as client:
        response = client.post("/client-nav", headers={"HX-Request": "true"})

    assert response.status_code == 204
    assert response.headers["HX-Location"] == "/y"
    assert "HX-Redirect" not in response.headers


def test_configured_jinja_globals_and_filters_reach_the_request_session():
    """The middleware builds its own session so it can attach the render hooks,
    which means request_scope()'s settings-seeding branch never runs for a
    FastAPI app — the middleware has to seed that session itself."""
    from pyjinhx.session import current_session

    def site_name() -> str:
        return "pyjinhx"

    app = FastAPI()
    apply_setup(
        app,
        _settings(
            jinja_globals={"site_name": site_name},
            jinja_filters={"shout": str.upper},
        ),
    )

    @app.get("/render")
    def render():
        session = current_session()
        assert session is not None
        # "b"|upper is Jinja's own builtin filter: the extras are added to the
        # environment, never swapped in for it.
        template = session.jinja_env.from_string(
            "{{ site_name() }}|{{ 'ok'|shout }}|{{ 'b'|upper }}"
        )
        return PlainTextResponse(template.render())

    with TestClient(app) as client:
        response = client.get("/render")

    assert response.status_code == 200
    assert response.text == "pyjinhx|OK|B"


def test_middleware_sessions_share_the_cached_environment():
    """The middleware builds its own session so it can attach the render hooks,
    so it is also the place that has to adopt the cached environment — two
    requests must not each compile the app's templates from scratch."""
    from pyjinhx.config import current_settings
    from pyjinhx.session import _environment_for, current_session

    seen: list[object] = []

    app = FastAPI()
    apply_setup(app, _settings(jinja_globals={"x": 1}))

    @app.get("/render")
    def render():
        session = current_session()
        assert session is not None
        seen.append(session.jinja_env)
        return PlainTextResponse(session.jinja_env.from_string("{{ x }}").render())

    with TestClient(app) as client:
        assert client.get("/render").text == "1"
        assert client.get("/render").text == "1"
        # Inside the client block: the lifespan's shutdown resets the process
        # settings, and the cache keys on the settings instance that was live.
        expected = _environment_for(current_settings())

    assert seen == [expected, expected]


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
    app.router.routes.append(_FakeIncludedRoute([inner]))

    apply_setup(app, _settings())

    assert inner.dependant.call is not original_call
