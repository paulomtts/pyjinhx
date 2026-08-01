from pyjinhx2.reactive.cache import (
    cache_get,
    cache_has,
    cache_put,
    invalidate,
    make_key,
)
from pyjinhx2.session import get_cache_reverse, get_cache_store, request_scope


class Widget:
    pass


class OtherWidget:
    pass


def test_make_key_pairs_the_class_with_the_key():
    assert make_key(Widget, "todos") == (Widget, "todos")


def test_make_key_separates_the_same_key_under_different_classes():
    assert make_key(Widget, "todos") != make_key(OtherWidget, "todos")


def test_put_then_get_round_trips_the_value():
    with request_scope():
        cache_put(Widget, "todos", [1, 2, 3])
        assert cache_get(Widget, "todos") == [1, 2, 3]


def test_get_returns_none_on_a_miss():
    with request_scope():
        assert cache_get(Widget, "todos") is None


def test_has_is_false_on_a_miss_and_true_after_a_put():
    with request_scope():
        assert cache_has(Widget, "todos") is False
        cache_put(Widget, "todos", "loaded")
        assert cache_has(Widget, "todos") is True


def test_a_cached_falsy_value_is_distinguishable_from_a_miss():
    with request_scope():
        cache_put(Widget, "empty", None)
        cache_put(Widget, "zero", 0)
        assert cache_get(Widget, "empty") is None
        assert cache_has(Widget, "empty") is True
        assert cache_get(Widget, "zero") == 0
        assert cache_has(Widget, "zero") is True
        assert cache_has(Widget, "never-stored") is False


def test_put_overwrites_an_existing_entry():
    with request_scope():
        cache_put(Widget, "todos", "first")
        cache_put(Widget, "todos", "second")
        assert cache_get(Widget, "todos") == "second"


def test_entries_do_not_leak_across_requests():
    with request_scope():
        cache_put(Widget, "todos", "first request")
    with request_scope():
        assert cache_has(Widget, "todos") is False
        assert cache_get(Widget, "todos") is None


def test_the_same_key_under_two_classes_stays_separate():
    with request_scope():
        cache_put(Widget, "todos", "widget value")
        cache_put(OtherWidget, "todos", "other value")
        assert cache_get(Widget, "todos") == "widget value"
        assert cache_get(OtherWidget, "todos") == "other value"


def test_it_stores_into_the_session_cache_store():
    with request_scope():
        cache_put(Widget, "todos", "value")
        assert get_cache_store()[(Widget, "todos")] == "value"


def test_outside_a_request_scope_it_is_a_silent_no_op():
    cache_put(Widget, "todos", "dropped")
    assert cache_get(Widget, "todos") is None
    assert cache_has(Widget, "todos") is False


def test_any_hashable_key_is_accepted():
    with request_scope():
        cache_put(Widget, 42, "int key")
        cache_put(Widget, ("todo", 7), "tuple key")
        assert cache_get(Widget, 42) == "int key"
        assert cache_get(Widget, ("todo", 7)) == "tuple key"


def test_invalidate_evicts_an_entry_registered_under_the_dirtied_key():
    with request_scope():
        cache_put(Widget, "todos", "loaded", react_keys=["todos"])
        assert cache_has(Widget, "todos") is True
        invalidate(["todos"])
        assert cache_has(Widget, "todos") is False
        assert cache_get(Widget, "todos") is None


def test_invalidate_leaves_entries_registered_under_other_keys_alone():
    with request_scope():
        cache_put(Widget, "todos", "todo value", react_keys=["todos"])
        cache_put(OtherWidget, "users", "user value", react_keys=["users"])
        invalidate(["todos"])
        assert cache_has(Widget, "todos") is False
        assert cache_get(OtherWidget, "users") == "user value"


def test_invalidate_on_a_key_with_no_entries_is_a_no_op():
    with request_scope():
        cache_put(Widget, "todos", "loaded", react_keys=["todos"])
        invalidate(["nothing-depends-on-this"])
        assert cache_get(Widget, "todos") == "loaded"


def test_an_entry_registered_under_two_keys_is_evicted_by_either_one():
    with request_scope():
        cache_put(Widget, "todos", "loaded", react_keys={"todos", "users"})
        invalidate(["users"])
        assert cache_has(Widget, "todos") is False


def test_eviction_clears_the_entry_from_every_key_it_was_registered_under():
    with request_scope():
        cache_put(Widget, "todos", "loaded", react_keys={"todos", "users"})
        invalidate(["users"])
        assert get_cache_reverse() == {"todos": set(), "users": set()}
