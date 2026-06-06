import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from examples.reactive_todo import store
from examples.reactive_todo.app import app
from examples.reactive_todo.components import TodoCounter, TodoTotal
from pyjinhx import PJX_MOUNTED_HEADER, Renderer

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_env():
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(ROOT)
    store.reset()
    yield
    Renderer.set_default_environment(prev)


def _manifest(*entries):
    return {PJX_MOUNTED_HEADER: json.dumps(list(entries))}


def test_index_injects_runtime_and_stamps_regions():
    body = client.get("/").text
    assert "htmx.org" in body
    assert "htmx:configRequest" in body
    for region in ("todo-counter", "todo-total", "todo-clear"):
        assert f'data-pjx-id="{region}"' in body
    assert 'data-pjx-type="TodoCounter"' in body
    assert "3 left" in body and "3 total" in body


def test_toggle_swaps_changed_dependents():
    headers = _manifest(
        {"id": "todo-counter", "type": "TodoCounter", "hash": "stale"},
        {"id": "todo-clear", "type": "TodoClearButton", "hash": "stale"},
    )
    body = client.post("/todos/1/toggle", headers=headers).text
    assert 'id="todo-1"' in body and "done" in body
    assert "outerHTML:[data-pjx-id='todo-counter']" in body and "2 left" in body
    assert (
        "outerHTML:[data-pjx-id='todo-clear']" in body and "Clear completed (1)" in body
    )


def test_toggle_hash_gates_unchanged_total():
    fresh_total = TodoTotal.load()
    headers = _manifest(
        {"id": "todo-counter", "type": "TodoCounter", "hash": "stale"},
        {"id": "todo-total", "type": "TodoTotal", "hash": fresh_total.state_hash()},
    )
    body = client.post("/todos/1/toggle", headers=headers).text
    assert "outerHTML:[data-pjx-id='todo-counter']" in body
    assert "outerHTML:[data-pjx-id='todo-total']" not in body


def test_clear_completed_hash_gates_unchanged_counter():
    client.post("/todos/1/toggle", headers=_manifest())
    fresh_counter = TodoCounter.load()
    headers = _manifest(
        {
            "id": "todo-counter",
            "type": "TodoCounter",
            "hash": fresh_counter.state_hash(),
        },
        {"id": "todo-total", "type": "TodoTotal", "hash": "stale"},
    )
    body = client.post("/todos/clear-completed", headers=headers).text
    assert "outerHTML:[data-pjx-id='todo-counter']" not in body
    assert "outerHTML:[data-pjx-id='todo-total']" in body


def test_toggle_row_primary_reflects_mutation_despite_warm_cache():
    client.get("/")
    body = client.post("/rows/1/toggle").text
    primary = body.split("hx-swap-oob")[0]
    assert 'class="todo done"' in primary and "✓" in primary
    primary_off = client.post("/rows/1/toggle").text.split("hx-swap-oob")[0]
    assert 'class="todo done"' not in primary_off and "○" in primary_off


def test_unknown_mounted_region_is_ignored():
    body = client.post(
        "/todos/1/toggle",
        headers=_manifest({"id": "ghost", "type": "DoesNotExist", "hash": "x"}),
    ).text
    assert "ghost" not in body
