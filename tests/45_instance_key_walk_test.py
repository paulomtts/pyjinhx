from pyjinhx import oob_swaps
from pyjinhx import LoadCache

from tests.ui.reactive.user_row import UserRow  # noqa: F401


def _manifest():
    return [
        {"id": "user-row-1", "type": "UserRow", "key": "1", "hash": "stale"},
        {"id": "user-row-2", "type": "UserRow", "key": "2", "hash": "stale"},
        {"id": "user-row-3", "type": "UserRow", "key": "3", "hash": "stale"},
    ]


def test_instance_dirty_swaps_only_that_row():
    LoadCache.clear()
    out = str(oob_swaps({"user:2"}, _manifest()))
    assert "outerHTML:[data-pjx-id='user-row-2']" in out
    assert "outerHTML:[data-pjx-id='user-row-1']" not in out
    assert "outerHTML:[data-pjx-id='user-row-3']" not in out
    assert "Bob" in out


def test_collection_dirty_swaps_all_rows():
    LoadCache.clear()
    out = str(oob_swaps({"users"}, _manifest()))
    for rid in ("user-row-1", "user-row-2", "user-row-3"):
        assert f"outerHTML:[data-pjx-id='{rid}']" in out


def test_unrelated_dirty_swaps_nothing():
    LoadCache.clear()
    assert str(oob_swaps({"todos"}, _manifest())) == ""


def test_each_row_reloads_with_its_own_key():
    LoadCache.clear()
    out = str(oob_swaps({"user:1", "user:3"}, _manifest()))
    assert "Alice" in out and "Carol" in out and "Bob" not in out
