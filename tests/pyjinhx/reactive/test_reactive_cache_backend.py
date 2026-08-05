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
