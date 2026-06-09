from pyjinhx import LoadCache, oob_swaps

from tests.ui.reactive.user_row import UserRow  # noqa: F401


def _manifest():
    return [
        {"id": "user-row-1", "type": "UserRow", "load": "1", "hash": "stale"},
        {"id": "user-row-2", "type": "UserRow", "load": "2", "hash": "stale"},
        {"id": "user-row-3", "type": "UserRow", "load": "3", "hash": "stale"},
    ]


def test_users_dirty_swaps_all_rows():
    LoadCache.clear()
    out = str(oob_swaps({"users"}, _manifest()))
    for rid in ("user-row-1", "user-row-2", "user-row-3"):
        assert f"outerHTML:[data-pjx-id='{rid}']" in out


def test_unrelated_dirty_swaps_nothing():
    LoadCache.clear()
    assert str(oob_swaps({"todos"}, _manifest())) == ""


def test_missing_keyed_entity_emits_delete_oob():
    LoadCache.clear()
    manifest = [{"id": "user-row-9", "type": "UserRow", "load": "9", "hash": "stale"}]
    out = str(oob_swaps({"users"}, manifest))
    assert "delete:[data-pjx-id='user-row-9']" in out
    assert "outerHTML:[data-pjx-id='user-row-9']" not in out

