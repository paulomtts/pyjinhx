import json
from typing import Any

from markupsafe import Markup

from pyjinhx.client import PJX_MOUNTED_HEADER
from pyjinhx.reactive import oob_swaps
from pyjinhx.renderer import reactive_root_attrs
from tests.reactive_test_support import reactive_client, record_mutation
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.reactive.reactive_panel import ReactivePanel  # noqa: F401


class _FakeHeaders:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class _FakeRequest:
    def __init__(self, headers):
        self.headers = _FakeHeaders(headers)


def _manifest_json(*entries):
    return json.dumps(list(entries))


def test_oob_swaps_accepts_request_like_object():
    store.state["completed"] = 3
    request = _FakeRequest(
        {
            PJX_MOUNTED_HEADER: _manifest_json(
                {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
            )
        }
    )
    out = str(oob_swaps({"todos"}, request))
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (3)" in out


def test_oob_swaps_request_without_header_is_empty():
    request = _FakeRequest({})
    assert str(oob_swaps({"todos"}, request)) == ""


def test_oob_swaps_non_request_object_is_ignored():
    out = oob_swaps({"todos"}, object())
    assert isinstance(out, Markup)
    assert str(out) == ""


def test_oob_swaps_exclude_ids_skips_region():
    store.state["remaining"] = 2
    store.state["completed"] = 1
    manifest = [
        {"id": "counter", "type": "ReactiveCounter", "hash": "stale"},
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"},
    ]
    out = str(oob_swaps({"todos"}, manifest, exclude_ids={"counter"}))
    assert "outerHTML:[data-pjx-id='counter']" not in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out


def test_render_no_args_is_unchanged():
    counter = ReactiveCounter(id="counter", remaining=8)
    assert str(counter.render()) == str(counter._render())


def test_reactive_render_returns_primary_plus_dependents():
    store.state["completed"] = 5
    primary = ReactiveCounter(id="counter", remaining=2)
    manifest = [
        {"id": "counter", "type": "ReactiveCounter", "hash": "stale"},
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"},
    ]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(primary.render())
    assert "2 left" in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (5)" in out
    assert "outerHTML:[data-pjx-id='counter']" not in out


def test_reactive_render_with_backend():
    store.state["completed"] = 6
    primary = ReactiveCounter(id="counter", remaining=1)
    manifest = [
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
    ]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(primary.render())
    assert "1 left" in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out


def test_reactive_render_returns_markup():
    primary = ReactiveCounter(id="counter", remaining=1)
    with reactive_client([]):
        record_mutation("todos")
        result = primary.render()
    assert isinstance(result, Markup)


def test_reactive_render_does_not_escape_primary_html():
    store.state["completed"] = 1
    primary = ReactiveCounter(id="counter", remaining=2)
    manifest = [
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
    ]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(primary.render())
    assert "&lt;span" not in out and "&#34;" not in out
    assert '<span class="counter" data-pjx-id="counter"' in out


def test_reactive_root_attrs_returns_pjx_dict():
    attrs = reactive_root_attrs(ReactiveCounter(id="counter", remaining=0))
    assert attrs["data-pjx-id"] == "counter"
    assert attrs["data-pjx-type"] == "ReactiveCounter"
    assert "data-pjx-hash" in attrs
    assert "data-pjx-reacts" in attrs  # ReactiveCounter declares react={Keys.TODOS}


def test_reactive_root_attrs_empty_for_non_reactive():
    from pyjinhx.builtins import PJXBadge

    assert reactive_root_attrs(PJXBadge(id="b", label="x")) == {}


def test_reactive_root_carries_both_pjx_and_extra_attrs_on_one_root():
    inline_attrs: dict[str, Any] = {"hx-get": "/inc"}
    counter = ReactiveCounter(id="counter", remaining=0, **inline_attrs)
    out = str(counter.render())
    root_tag = out[: out.index(">") + 1]  # the single root's opening tag
    assert 'data-pjx-id="counter"' in root_tag
    assert 'hx-get="/inc"' in root_tag
    assert out.count('data-pjx-id="counter"') == 1  # stamped once, not twice
