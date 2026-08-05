import dataclasses

import pytest

from pyjinhx.reactive.backend import (
    MISS,
    CacheBackend,
    CachePolicy,
    InMemoryCacheBackend,
)


class FakeClock:
    """A monotonic clock the tests advance by hand instead of sleeping."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_in_memory_backend_satisfies_the_protocol():
    assert isinstance(InMemoryCacheBackend(), CacheBackend)


def test_get_on_an_empty_backend_returns_miss():
    backend = InMemoryCacheBackend()
    result = backend.get("pjx:1:app.Widget:todos")
    assert result is MISS
    assert result is not None


def test_miss_is_not_equal_to_any_ordinary_value():
    assert MISS is not None
    assert MISS != ""
    assert MISS != 0


def test_put_then_get_round_trips_the_value():
    backend = InMemoryCacheBackend()
    backend.put("todos", [1, 2, 3], tags=(), ttl=None)
    assert backend.get("todos") == [1, 2, 3]


def test_the_stored_object_is_the_same_object():
    backend = InMemoryCacheBackend()
    value = object()
    backend.put("todos", value, tags=(), ttl=None)
    assert backend.get("todos") is value


def test_a_cached_none_round_trips_as_none_not_miss():
    backend = InMemoryCacheBackend()
    backend.put("todos", None, tags=(), ttl=None)
    assert backend.get("todos") is None


def test_put_on_an_existing_key_overwrites_the_value():
    backend = InMemoryCacheBackend()
    backend.put("todos", "first", tags=(), ttl=None)
    backend.put("todos", "second", tags=(), ttl=None)
    assert backend.get("todos") == "second"


def test_keys_do_not_share_an_entry():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=(), ttl=None)
    backend.put("users", "b", tags=(), ttl=None)
    assert backend.get("todos") == "a"
    assert backend.get("users") == "b"


def test_clear_empties_the_store():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=(), ttl=None)
    backend.put("users", "b", tags=(), ttl=None)
    backend.clear()
    assert backend.get("todos") is MISS
    assert backend.get("users") is MISS


def test_evict_drops_an_entry_carrying_the_tag():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list",), ttl=None)
    backend.evict(("todo-list",))
    assert backend.get("todos") is MISS


def test_evict_leaves_entries_with_no_overlapping_tag_alone():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list",), ttl=None)
    backend.put("users", "b", tags=("user-list",), ttl=None)
    backend.evict(("todo-list",))
    assert backend.get("users") == "b"


def test_an_entry_with_several_tags_is_evicted_by_any_one_of_them():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list", "user-list"), ttl=None)
    backend.evict(("user-list",))
    assert backend.get("todos") is MISS


def test_evict_drops_every_entry_matching_any_given_tag():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list",), ttl=None)
    backend.put("users", "b", tags=("user-list",), ttl=None)
    backend.put("stats", "c", tags=("stats",), ttl=None)
    backend.evict(("todo-list", "user-list"))
    assert backend.get("todos") is MISS
    assert backend.get("users") is MISS
    assert backend.get("stats") == "c"


def test_an_entry_reachable_from_two_evicted_tags_is_dropped_once():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list", "user-list"), ttl=None)
    backend.evict(("todo-list", "user-list"))
    assert backend.get("todos") is MISS


def test_re_putting_a_key_drops_its_old_tags():
    backend = InMemoryCacheBackend()
    backend.put("todos", "first", tags=("todo-list",), ttl=None)
    backend.put("todos", "second", tags=("user-list",), ttl=None)
    backend.evict(("todo-list",))
    assert backend.get("todos") == "second"


def test_evict_with_no_tags_is_a_no_op():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list",), ttl=None)
    backend.evict(())
    assert backend.get("todos") == "a"


def test_evict_on_an_unknown_tag_is_a_no_op():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list",), ttl=None)
    backend.evict(("nothing-uses-this",))
    assert backend.get("todos") == "a"


def test_evict_on_an_empty_backend_is_a_no_op():
    backend = InMemoryCacheBackend()
    backend.evict(("todo-list",))
    assert backend.get("todos") is MISS


def test_clear_drops_the_tag_index_too():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=("todo-list",), ttl=None)
    backend.clear()
    backend.put("todos", "b", tags=(), ttl=None)
    backend.evict(("todo-list",))
    assert backend.get("todos") == "b"


def test_a_ttl_none_entry_never_expires():
    clock = FakeClock()
    backend = InMemoryCacheBackend(clock=clock)
    backend.put("todos", "a", tags=(), ttl=None)
    clock.advance(1_000_000.0)
    assert backend.get("todos") == "a"


def test_an_entry_is_a_hit_before_its_ttl_elapses():
    clock = FakeClock()
    backend = InMemoryCacheBackend(clock=clock)
    backend.put("todos", "a", tags=(), ttl=60.0)
    clock.advance(59.0)
    assert backend.get("todos") == "a"


def test_an_entry_becomes_a_miss_once_its_ttl_elapses():
    clock = FakeClock()
    backend = InMemoryCacheBackend(clock=clock)
    backend.put("todos", "a", tags=(), ttl=60.0)
    clock.advance(61.0)
    assert backend.get("todos") is MISS


def test_an_expired_none_is_a_miss_not_a_cached_none():
    clock = FakeClock()
    backend = InMemoryCacheBackend(clock=clock)
    backend.put("todos", None, tags=(), ttl=60.0)
    clock.advance(61.0)
    assert backend.get("todos") is MISS


def test_re_putting_an_expired_key_makes_it_a_hit_again():
    clock = FakeClock()
    backend = InMemoryCacheBackend(clock=clock)
    backend.put("todos", "a", tags=(), ttl=60.0)
    clock.advance(61.0)
    backend.put("todos", "b", tags=(), ttl=60.0)
    assert backend.get("todos") == "b"


def test_evict_drops_an_expired_entry_that_was_never_looked_up():
    clock = FakeClock()
    backend = InMemoryCacheBackend(clock=clock)
    backend.put("todos", "a", tags=("todo-list",), ttl=60.0)
    clock.advance(61.0)
    backend.evict(("todo-list",))
    backend.put("todos", "b", tags=(), ttl=None)
    backend.evict(("todo-list",))
    assert backend.get("todos") == "b"


def test_expiry_frees_the_entrys_tag_memberships():
    clock = FakeClock()
    backend = InMemoryCacheBackend(clock=clock)
    backend.put("todos", "a", tags=("todo-list",), ttl=60.0)
    clock.advance(61.0)
    assert backend.get("todos") is MISS
    backend.put("todos", "b", tags=(), ttl=None)
    backend.evict(("todo-list",))
    assert backend.get("todos") == "b"


def test_the_default_clock_is_monotonic_and_does_not_expire_instantly():
    backend = InMemoryCacheBackend()
    backend.put("todos", "a", tags=(), ttl=60.0)
    assert backend.get("todos") == "a"


def test_cache_policy_defaults_to_a_finite_ttl():
    assert CachePolicy().ttl == 300


def test_cache_policy_accepts_an_explicit_ttl():
    assert CachePolicy(ttl=60).ttl == 60


def test_cache_policy_accepts_an_explicit_none_ttl():
    assert CachePolicy(ttl=None).ttl is None


def test_cache_policy_is_frozen():
    policy = CachePolicy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.ttl = 60  # type: ignore[misc]


def test_cache_policies_compare_by_value():
    assert CachePolicy(ttl=60) == CachePolicy(ttl=60)
    assert CachePolicy(ttl=60) != CachePolicy(ttl=300)
    assert CachePolicy() == CachePolicy(ttl=300)


def test_cache_policy_has_exactly_one_field():
    names = [field.name for field in dataclasses.fields(CachePolicy)]
    assert names == ["ttl"]
