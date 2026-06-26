from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from pyjinhx import setup
from pyjinhx.reactive import ReactiveResponse
from tests.reactive_test_support import Keys


def _reswap_app() -> FastAPI:
    app = FastAPI()
    setup(app)

    @app.get("/nav", response_class=HTMLResponse)
    def nav():
        return ReactiveResponse(Keys.TODOS)  # OOB-only reactive trigger response

    @app.get("/with-primary", response_class=HTMLResponse)
    def with_primary():
        return ReactiveResponse(Keys.TODOS, html="<div>primary</div>")

    @app.get("/plain", response_class=HTMLResponse)
    def plain():
        return "<div>hello</div>"

    return app


def test_oob_only_reactive_response_gets_hx_reswap_none():
    with TestClient(_reswap_app()) as client:
        resp = client.get("/nav")
    assert resp.status_code == 200
    assert resp.headers.get("HX-Reswap") == "none"


def test_reactive_response_with_primary_html_has_no_reswap_header():
    with TestClient(_reswap_app()) as client:
        resp = client.get("/with-primary")
    assert resp.status_code == 200
    assert "HX-Reswap" not in resp.headers


def test_plain_response_has_no_reswap_header():
    with TestClient(_reswap_app()) as client:
        resp = client.get("/plain")
    assert resp.status_code == 200
    assert "HX-Reswap" not in resp.headers


from fastapi.responses import RedirectResponse, Response


def _redirect_app(*, htmx_redirects: bool) -> FastAPI:
    app = FastAPI()
    setup(app, htmx_redirects=htmx_redirects)

    @app.post("/logout")
    def logout():
        resp = RedirectResponse("/login", status_code=303)
        resp.set_cookie("session", "", max_age=0)
        return resp

    @app.get("/cond")
    def cond():
        return Response(status_code=304)

    return app


def test_htmx_redirect_rewritten_to_204_preserving_cookie():
    with TestClient(_redirect_app(htmx_redirects=True)) as client:
        resp = client.post(
            "/logout", headers={"HX-Request": "true"}, follow_redirects=False
        )
    assert resp.status_code == 204
    assert resp.headers["HX-Redirect"] == "/login"
    assert "location" not in resp.headers
    assert resp.headers.get("set-cookie") is not None  # cookie preserved


def test_304_is_not_rewritten():
    with TestClient(_redirect_app(htmx_redirects=True)) as client:
        resp = client.get(
            "/cond", headers={"HX-Request": "true"}, follow_redirects=False
        )
    assert resp.status_code == 304
    assert "HX-Redirect" not in resp.headers


def test_non_htmx_redirect_passes_through():
    with TestClient(_redirect_app(htmx_redirects=True)) as client:
        resp = client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert "HX-Redirect" not in resp.headers


def test_redirect_passes_through_when_flag_off():
    with TestClient(_redirect_app(htmx_redirects=False)) as client:
        resp = client.post(
            "/logout", headers={"HX-Request": "true"}, follow_redirects=False
        )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert "HX-Redirect" not in resp.headers
