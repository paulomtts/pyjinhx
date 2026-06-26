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
