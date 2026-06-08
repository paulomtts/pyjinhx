from typing import ClassVar

from pyjinhx import LoadCache, ReactiveComponent

load_calls = {"n": 0}


class Row(ReactiveComponent):
    title: str = ""
    reacts_to: ClassVar[set[str]] = {"row", "rows"}

    @classmethod
    def load(cls, key: str | int) -> "Row":
        load_calls["n"] += 1
        return cls(title=f"row {key}")


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
    r = Row.load(42)  # int in
    assert r.id == "row-42" and r._pjx_key == "42"


def test_cache_is_per_key():
    _reset()
    Row.load("1")
    Row.load("2")
    Row.load("1")  # hit
    assert load_calls["n"] == 2


def test_instance_invalidation_evicts_one_row():
    _reset()
    Row.load("1")
    Row.load("2")
    LoadCache.invalidate({"row:1"})
    Row.load("1")  # miss -> reload
    Row.load("2")  # still cached
    assert load_calls["n"] == 3


def test_stem_invalidation_evicts_matching_instance_keys():
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
    LoadCache.invalidate({"rows"})  # both rows declare "rows"
    Row.load("1")
    Row.load("2")
    assert load_calls["n"] == 4
