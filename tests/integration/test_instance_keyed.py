import json
from pathlib import Path

import pytest

from examples.reactive_todo import store
from examples.reactive_todo.components import ItemRow
from pyjinhx import PJX_MOUNTED_HEADER, Renderer

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolated_env():
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
            "id": f"row-{i}",
            "type": "ItemRow",
            "load": str(i),
            "hash": ItemRow.load(i).state_hash(),
        }
        for i in ids
    ]


def test_index_renders_instance_keyed_rows(client):
    body = client.get("/").text
    for i in (1, 2, 3):
        assert f'data-pjx-id="row-{i}"' in body
        assert f'data-pjx-load="{i}"' in body
    assert 'data-pjx-type="ItemRow"' in body


def test_toggle_row_swaps_only_that_row(client):
    headers = _manifest(*_rows(1, 2, 3))
    body = client.post("/rows/1/toggle", headers=headers).text

    assert 'data-pjx-id="row-1"' in body
    assert 'data-pjx-load="1"' in body

    assert "outerHTML:[data-pjx-id='row-1']" not in body
    assert "outerHTML:[data-pjx-id='row-2']" not in body
    assert "outerHTML:[data-pjx-id='row-3']" not in body


def test_toggle_row_does_not_resurrect_other_rows_as_oob(client):
    headers = _manifest(*_rows(1, 2, 3))
    body = client.post("/rows/2/toggle", headers=headers).text

    assert 'data-pjx-id="row-2"' in body
    assert 'data-pjx-load="2"' in body
    assert "outerHTML:[data-pjx-id='row-1']" not in body
    assert "outerHTML:[data-pjx-id='row-3']" not in body
