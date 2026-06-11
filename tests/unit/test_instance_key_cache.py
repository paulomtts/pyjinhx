from typing import Annotated

from pyjinhx import MutationKey, PjxKey, ReactiveComponent
from pyjinhx.cache import LoadCache

load_calls = {"n": 0}


class Keys(MutationKey):
    ROW = "row"
    ROWS = "rows"


class Row(ReactiveComponent, react={Keys.ROW, Keys.ROWS}):
    row_key: Annotated[str, PjxKey()]
    title: str = ""

    @classmethod
    def load(cls, key: str | int) -> "Row":
        load_calls["n"] += 1
        return cls(row_key=str(key), title=f"row {key}")


def _reset():
    LoadCache.clear()
    load_calls["n"] = 0


def test_keyedness_detected_from_signature():
    assert Row._pjx_keyed is True


def test_keyed_id_and_key_stashed():
    _reset()
    r = Row.load("42")
    assert r.id == "row-42"
    assert r._pjx_key == "42"
    assert r.title == "row 42"


def test_key_is_coerced_to_string():
    _reset()
    r = Row.load(42)
    assert r.id == "row-42" and r._pjx_key == "42"


def test_cache_is_per_key():
    _reset()
    Row.load("1")
    Row.load("2")
    Row.load("1")
    assert load_calls["n"] == 2


def test_row_stem_invalidation_evicts_all_rows():
    _reset()
    Row.load("1")
    Row.load("2")
    LoadCache.invalidate({"row"})
    Row.load("1")
    Row.load("2")
    assert load_calls["n"] == 4


def test_collection_invalidation_evicts_all_rows():
    _reset()
    Row.load("1")
    Row.load("2")
    LoadCache.invalidate({"rows"})
    Row.load("1")
    Row.load("2")
    assert load_calls["n"] == 4


def test_unrelated_key_does_not_evict():
    _reset()
    Row.load("1")
    LoadCache.invalidate({"other"})
    Row.load("1")
    assert load_calls["n"] == 1
