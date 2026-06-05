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
    # The shared conftest clears the load cache + instance registry around every test;
    # here we additionally pin the default Jinja environment to the repo root (so the
    # app's templates resolve regardless of CWD) and reset the demo's in-memory store.
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(ROOT)
    store.reset()
    yield
    Renderer.set_default_environment(prev)


def _manifest(*entries):
    return {PJX_MOUNTED_HEADER: json.dumps(list(entries))}


def test_index_injects_runtime_and_stamps_regions():
    body = client.get("/").text
    assert "htmx.org" in body  # htmx loaded by the shell
    assert "htmx:configRequest" in body  # pjx.js injected via base_layout
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
    assert 'id="todo-1"' in body and "done" in body  # primary row, now done
    assert "outerHTML:[data-pjx-id='todo-counter']" in body and "2 left" in body
    assert (
        "outerHTML:[data-pjx-id='todo-clear']" in body and "Clear completed (1)" in body
    )


def test_toggle_hash_gates_unchanged_total():
    # A toggle doesn't change the total; if the client reports the current total hash,
    # the walk must skip it.
    fresh_total = TodoTotal.load()  # id is already "todo-total"
    headers = _manifest(
        {"id": "todo-counter", "type": "TodoCounter", "hash": "stale"},
        {"id": "todo-total", "type": "TodoTotal", "hash": fresh_total.state_hash()},
    )
    body = client.post("/todos/1/toggle", headers=headers).text
    assert "outerHTML:[data-pjx-id='todo-counter']" in body  # changed -> swapped
    assert "outerHTML:[data-pjx-id='todo-total']" not in body  # unchanged -> skipped


def test_clear_completed_hash_gates_unchanged_counter():
    client.post("/todos/1/toggle", headers=_manifest())  # mark #1 done
    fresh_counter = TodoCounter.load()  # remaining is unchanged by clearing completed
    headers = _manifest(
        {
            "id": "todo-counter",
            "type": "TodoCounter",
            "hash": fresh_counter.state_hash(),
        },
        {"id": "todo-total", "type": "TodoTotal", "hash": "stale"},
    )
    body = client.post("/todos/clear-completed", headers=headers).text
    assert "outerHTML:[data-pjx-id='todo-counter']" not in body  # unchanged -> skipped
    assert "outerHTML:[data-pjx-id='todo-total']" in body  # total changed -> swapped


def test_unknown_mounted_region_is_ignored():
    body = client.post(
        "/todos/1/toggle",
        headers=_manifest({"id": "ghost", "type": "DoesNotExist", "hash": "x"}),
    ).text
    assert "ghost" not in body
