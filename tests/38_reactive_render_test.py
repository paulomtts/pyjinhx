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
