from pyjinhx.reactive.backend import MISS, CacheBackend, InMemoryCacheBackend


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
