from pyjinhx.cache import LoadCache
from pyjinhx.keys import reactive_key
from pyjinhx.reactive import oob_swaps

from tests.ui.reactive.counted_row import CountedRow, Keys  # noqa: F401


def _manifest():
    return [
        {"id": "row-1", "type": "CountedRow", "load": "1", "hash": "stale"},
        {"id": "row-2", "type": "CountedRow", "load": "2", "hash": "stale"},
        {"id": "row-3", "type": "CountedRow", "load": "3", "hash": "stale"},
    ]


def setup_function():
    LoadCache.clear()
    CountedRow.load_calls.clear()


def test_static_key_dirty_still_reloads_every_row():
    out = str(oob_swaps({"row"}, _manifest()))
    assert sorted(CountedRow.load_calls) == ["1", "2", "3"]
    for rid in ("row-1", "row-2", "row-3"):
        assert f"outerHTML:[data-pjx-id='{rid}']" in out


def test_dynamic_key_dirty_reloads_only_the_matching_row():
    out = str(oob_swaps({reactive_key(Keys.ROW, "2")}, _manifest()))
    assert CountedRow.load_calls == ["2"]
    assert "outerHTML:[data-pjx-id='row-2']" in out
    assert "outerHTML:[data-pjx-id='row-1']" not in out
    assert "outerHTML:[data-pjx-id='row-3']" not in out


def test_unrelated_dynamic_key_reloads_nothing():
    out = str(oob_swaps({reactive_key(Keys.ROW, "999")}, _manifest()))
    assert CountedRow.load_calls == []
    assert out == ""
