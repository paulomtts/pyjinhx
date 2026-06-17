import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from pyjinhx import setup
from pyjinhx.client import PJX_MOUNTED_HEADER
from pyjinhx.mutations import MutationTracker
from pyjinhx.reactive import ReactiveResponse
from pyjinhx.renderer import Renderer
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401 (registers)
from tests.ui.unified_component import UnifiedComponent  # noqa: F401 (registers)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _app() -> FastAPI:
    app = FastAPI()
    setup(app)

    @app.post("/act", response_class=HTMLResponse)
    def act():
        # A controller dirties a key, then returns a NON-reactive result view.
        store.state["remaining"] = 7
        MutationTracker.record(("todos",))
        return str(UnifiedComponent(id="result", text="done").render())

    @app.post("/reactive", response_class=HTMLResponse)
    def reactive():
        store.state["remaining"] = 7
        MutationTracker.record(("todos",))
        return str(ReactiveCounter.render())

    @app.post("/dismiss", response_class=HTMLResponse)
    def dismiss():
        # Renders no component; ReactiveResponse fans out the dependents OOB.
        store.state["remaining"] = 7
        MutationTracker.record(("todos",))
        return str(ReactiveResponse("<p>no component here</p>"))

    return app


def test_nonreactive_response_carries_oob_swaps():
    Renderer.set_default_environment(REPO_ROOT)
    manifest = json.dumps([{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}])
    with TestClient(_app()) as client:
        resp = client.post("/act", headers={PJX_MOUNTED_HEADER: manifest})
    body = resp.text
    assert resp.status_code == 200
    assert 'id="result"' in body
    assert "done" in body
    assert "outerHTML:[data-pjx-id='counter']" in body
    assert "7 left" in body


def test_reactive_response_emits_single_swap_set():
    Renderer.set_default_environment(REPO_ROOT)
    manifest = json.dumps([{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}])
    with TestClient(_app()) as client:
        resp = client.post("/reactive", headers={PJX_MOUNTED_HEADER: manifest})
    body = resp.text
    assert "7 left" in body
    assert "outerHTML:[data-pjx-id='counter']" not in body


def test_dismiss_keeps_primary_and_appends_single_swap_set():
    Renderer.set_default_environment(REPO_ROOT)
    manifest = json.dumps([{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}])
    with TestClient(_app()) as client:
        resp = client.post("/dismiss", headers={PJX_MOUNTED_HEADER: manifest})
    body = resp.text
    assert resp.status_code == 200
    assert "<p>no component here</p>" in body
    assert "7 left" in body
    assert body.count("outerHTML:[data-pjx-id='counter']") == 1
