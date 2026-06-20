import json
from pathlib import Path

import pytest

from examples.reactive_todo import store
from examples.reactive_todo.counter import Counter
from examples.reactive_todo.total import Total
from pyjinhx import Renderer
from pyjinhx.client import PJX_MOUNTED_HEADER

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


@pytest.mark.pjx_runtime
def test_index_injects_runtime_and_stamps_regions(client):
    body = client.get("/").text
    assert "htmx.org" in body
    assert "htmx:configRequest" in body
    for region in ("counter", "total", "clear"):
        assert f'data-pjx-id="{region}"' in body
    assert 'data-pjx-type="Counter"' in body
    assert "3 left" in body and "3 total" in body


def test_toggle_swaps_changed_dependents(client):
    headers = _manifest(
        {"id": "counter", "type": "Counter", "hash": "stale"},
        {"id": "clear", "type": "ClearButton", "hash": "stale"},
    )
    body = client.post("/rows/1/toggle", headers=headers).text
    assert 'data-pjx-id="row-1"' in body and "done" in body
    assert "outerHTML:[data-pjx-id='counter']" in body and "2 left" in body
    assert (
        "outerHTML:[data-pjx-id='clear']" in body and "Clear completed (1)" in body
    )


def test_toggle_does_not_reswap_whole_list(client):
    # regression: a full-list swap on toggle detaches a concurrent row's target
    headers = _manifest(
        {"id": "list", "type": "ItemList", "hash": "stale"},
        {"id": "row-1", "type": "ItemRow", "load": "1", "hash": "stale"},
        {"id": "row-2", "type": "ItemRow", "load": "2", "hash": "stale"},
    )
    body = client.post("/rows/1/toggle", headers=headers).text
    assert 'data-pjx-id="row-1"' in body
    assert "outerHTML:[data-pjx-id='list']" not in body


def test_toggle_hash_gates_unchanged_total(client):
    fresh_total = Total.load()
    headers = _manifest(
        {"id": "counter", "type": "Counter", "hash": "stale"},
        {"id": "total", "type": "Total", "hash": fresh_total.state_hash()},
    )
    body = client.post("/rows/1/toggle", headers=headers).text
    assert "outerHTML:[data-pjx-id='counter']" in body
    assert "outerHTML:[data-pjx-id='total']" not in body


def test_clear_completed_with_stale_row_manifest(client):
    client.post("/rows/1/toggle", headers=_manifest())
    headers = _manifest(
        {"id": "row-1", "type": "ItemRow", "load": "1", "hash": "stale"},
        {"id": "list", "type": "ItemList", "hash": "stale"},
    )
    body = client.post("/todos/clear-completed", headers=headers).text
    assert 'id="list"' in body
    assert "row-1" not in body.split("hx-swap-oob")[0]
    assert "delete:[data-pjx-id='row-1']" in body


def test_clear_completed_hash_gates_unchanged_counter(client):
    client.post("/rows/1/toggle", headers=_manifest())
    fresh_counter = Counter.load()
    headers = _manifest(
        {
            "id": "counter",
            "type": "Counter",
            "hash": fresh_counter.state_hash(),
        },
        {"id": "total", "type": "Total", "hash": "stale"},
    )
    body = client.post("/todos/clear-completed", headers=headers).text
    assert "outerHTML:[data-pjx-id='counter']" not in body
    assert "outerHTML:[data-pjx-id='total']" in body


def test_toggle_row_primary_reflects_mutation_despite_warm_cache(client):
    client.get("/")
    body = client.post("/rows/1/toggle").text
    primary = body.split("hx-swap-oob")[0]
    assert 'class="todo done"' in primary and "✓" in primary
    primary_off = client.post("/rows/1/toggle").text.split("hx-swap-oob")[0]
    assert 'class="todo done"' not in primary_off and "○" in primary_off


def test_unknown_mounted_region_is_ignored(client):
    body = client.post(
        "/rows/1/toggle",
        headers=_manifest({"id": "ghost", "type": "DoesNotExist", "hash": "x"}),
    ).text
    assert "ghost" not in body


def test_components_are_single_file():
    assert Counter._pjx_source_path.endswith("counter.pjx")
    assert Total._pjx_source_path.endswith("total.pjx")
