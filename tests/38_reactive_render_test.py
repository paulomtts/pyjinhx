import json

from markupsafe import Markup

from pyjinhx import PJX_MOUNTED_HEADER, oob_swaps
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401 (used by Task 2 tests)
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.reactive.reactive_panel import ReactivePanel  # noqa: F401


class _FakeHeaders:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class _FakeRequest:
    """Minimal request-like object: exposes .headers.get(), no FastAPI import."""

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
    request = _FakeRequest({})  # header absent -> headers.get returns None
    assert str(oob_swaps({"todos"}, request)) == ""


def test_oob_swaps_non_request_object_is_ignored():
    out = oob_swaps({"todos"}, object())  # not str/list/None/request-like
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
    out = str(primary.render(dirtied={"todos"}, mounted=manifest))
    assert "2 left" in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (5)" in out
    assert "outerHTML:[data-pjx-id='counter']" not in out


def test_reactive_render_with_request_object():
    store.state["completed"] = 6
    primary = ReactiveCounter(id="counter", remaining=1)
    request = _FakeRequest(
        {
            PJX_MOUNTED_HEADER: _manifest_json(
                {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
            )
        }
    )
    out = str(primary.render(dirtied={"todos"}, mounted=request))
    assert "1 left" in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out


def test_reactive_render_returns_markup():
    primary = ReactiveCounter(id="counter", remaining=1)
    result = primary.render(dirtied={"todos"}, mounted=[])
    assert isinstance(result, Markup)


def test_reactive_render_does_not_escape_primary_html():
    store.state["completed"] = 1
    primary = ReactiveCounter(id="counter", remaining=2)
    out = str(
        primary.render(
            dirtied={"todos"},
            mounted=[{"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}],
        )
    )
    assert "&lt;span" not in out and "&#34;" not in out
    assert '<span class="counter" data-pjx-id="counter"' in out
