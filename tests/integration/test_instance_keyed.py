import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from examples.reactive_todo import store
from examples.reactive_todo.app import app
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


def _rows(*ids):
    return [
        {
            "id": f"todo-item-row-{i}",
            "type": "TodoItemRow",
            "key": str(i),
            "hash": "stale",
        }
        for i in ids
    ]


def test_index_renders_instance_keyed_rows():
    body = client.get("/").text
    for i in (1, 2, 3):
        assert f'data-pjx-id="todo-item-row-{i}"' in body
        assert f'data-pjx-key="{i}"' in body
    assert 'data-pjx-type="TodoItemRow"' in body


def test_toggle_row_swaps_only_that_row():
    headers = _manifest(*_rows(1, 2, 3))
    body = client.post("/rows/1/toggle", headers=headers).text

    # The primary response is the toggled row as raw HTML, stamped with its key.
    assert 'data-pjx-id="todo-item-row-1"' in body
    assert 'data-pjx-key="1"' in body

    # No other row is swapped: only the (excluded) primary row is present, and
    # rows 2 and 3 are left untouched.
    assert "outerHTML:[data-pjx-id='todo-item-row-1']" not in body  # primary, not OOB
    assert "outerHTML:[data-pjx-id='todo-item-row-2']" not in body
    assert "outerHTML:[data-pjx-id='todo-item-row-3']" not in body


def test_toggle_row_does_not_resurrect_other_rows_as_oob():
    # Even when sibling rows are mounted, dirtying "todo:1" must not emit OOB swaps
    # for rows 2 or 3 (their instance key never enters dirtied).
    headers = _manifest(*_rows(1, 2, 3))
    body = client.post("/rows/2/toggle", headers=headers).text

    assert 'data-pjx-id="todo-item-row-2"' in body  # primary row 2
    assert 'data-pjx-key="2"' in body
    assert "outerHTML:[data-pjx-id='todo-item-row-1']" not in body
    assert "outerHTML:[data-pjx-id='todo-item-row-3']" not in body
