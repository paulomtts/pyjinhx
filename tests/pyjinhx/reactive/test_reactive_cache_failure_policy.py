"""A raising tier-2 backend degrades the cache instead of failing the request."""

import logging
from typing import Annotated

import pytest

from pyjinhx.config import configure_pyjinhx, current_settings
from pyjinhx.reactive.backend import InMemoryCacheBackend
from pyjinhx.reactive.backend_health import is_degraded, reset_backend_health
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.session import request_scope


class BrokenBackend(InMemoryCacheBackend):
    """An in-memory backend whose chosen methods raise instead of working."""

    def __init__(
        self,
        *,
        fail_get: bool = False,
        fail_put: bool = False,
        fail_evict: bool = False,
    ) -> None:
        super().__init__()
        self.fail_get = fail_get
        self.fail_put = fail_put
        self.fail_evict = fail_evict
        self.gets: list[str] = []
        self.puts: list[str] = []
        self.evicts: list[tuple[str, ...]] = []

    def get(self, key: str) -> object:
        self.gets.append(key)
        if self.fail_get:
            raise RuntimeError("get is down")
        return super().get(key)

    def put(self, key: str, value: object, *, tags, ttl) -> None:
        self.puts.append(key)
        if self.fail_put:
            raise RuntimeError("put is down")
        super().put(key, value, tags=tags, ttl=ttl)

    def evict(self, tags) -> None:
        collected = tuple(tags)
        self.evicts.append(collected)
        if self.fail_evict:
            raise RuntimeError("evict is down")
        super().evict(collected)


@pytest.fixture(autouse=True)
def clean_health():
    """Backend health is process-wide: no test may inherit another's flags."""
    reset_backend_health()
    yield
    reset_backend_health()


def publish[B](backend: B) -> B:
    """Publish a backend into the process settings and return it."""
    configure_pyjinhx(current_settings().merge(cache_backend=backend))
    return backend


@pytest.fixture
def settings_restored():
    """Restore whatever settings the process had before this test."""
    previous = current_settings()
    yield
    configure_pyjinhx(previous)


def make_row_class(calls: list[int]):
    """A reactive component whose load() records every call it really ran."""

    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    return Row


def test_a_raising_get_falls_through_to_the_real_load(settings_restored: None):
    publish(BrokenBackend(fail_get=True))
    calls: list[int] = []
    Row = make_row_class(calls)

    with request_scope():
        loaded = Row.load(7)

    assert loaded.row_id == 7
    assert calls == [7]


def test_a_raising_get_warns_once_across_many_requests(
    settings_restored: None, caplog: pytest.LogCaptureFixture
):
    publish(BrokenBackend(fail_get=True))
    calls: list[int] = []
    Row = make_row_class(calls)

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        for _ in range(3):
            with request_scope():
                Row.load(7)

    assert calls == [7, 7, 7]
    assert len(caplog.records) == 1


def test_a_degraded_backend_is_not_even_asked_for_a_get(settings_restored: None):
    backend = publish(BrokenBackend(fail_evict=True))
    calls: list[int] = []
    Row = make_row_class(calls)

    # A failed eviction is what degrades the backend.
    with request_scope():
        Row.load(7)
    from pyjinhx.reactive.cache import invalidate

    with request_scope():
        invalidate(["rows:7"])

    assert is_degraded(backend) is True
    backend.gets.clear()

    with request_scope():
        Row.load(7)

    assert backend.gets == []
    assert calls == [7, 7]


def test_a_raising_put_drops_the_write_without_touching_the_result(
    settings_restored: None,
):
    publish(BrokenBackend(fail_put=True))
    calls: list[int] = []
    Row = make_row_class(calls)

    with request_scope():
        loaded = Row.load(7)

    assert loaded.row_id == 7
    assert calls == [7]


def test_a_raising_put_warns_once_and_never_degrades_the_backend(
    settings_restored: None, caplog: pytest.LogCaptureFixture
):
    backend = publish(BrokenBackend(fail_put=True))
    calls: list[int] = []
    Row = make_row_class(calls)

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        for _ in range(3):
            with request_scope():
                Row.load(7)

    assert len(caplog.records) == 1
    # Only a failed eviction can degrade a backend: a dropped write costs
    # speed, not correctness, so reads keep being tried.
    assert is_degraded(backend) is False
    assert backend.gets != []


def test_a_landed_write_clears_the_degraded_flag(settings_restored: None):
    backend = publish(BrokenBackend())
    calls: list[int] = []
    Row = make_row_class(calls)

    from pyjinhx.reactive.backend_health import note_failure

    note_failure(backend, "evict", RuntimeError("boom"), degrade=True)
    assert is_degraded(backend) is True

    with request_scope():
        Row.load(7)

    assert is_degraded(backend) is False


def test_a_raising_evict_still_clears_tier_one(settings_restored: None):
    publish(BrokenBackend(fail_evict=True))
    calls: list[int] = []
    Row = make_row_class(calls)

    from pyjinhx.reactive.cache import invalidate
    from pyjinhx.reactive.component import _cache_key

    with request_scope():
        Row.load(7)
        key = _cache_key(Row, {"row_id": 7}, protocol_mode=False)

        invalidate(["rows:7"])

        from pyjinhx.reactive.cache import cache_has

        assert cache_has(Row, key) is False


def test_a_raising_evict_degrades_the_backend_and_warns_once(
    settings_restored: None, caplog: pytest.LogCaptureFixture
):
    backend = publish(BrokenBackend(fail_evict=True))

    from pyjinhx.reactive.cache import invalidate

    with caplog.at_level(logging.WARNING, logger="pyjinhx"), request_scope():
        invalidate(["rows:7"])
        invalidate(["rows:8"])

    assert is_degraded(backend) is True
    assert len(caplog.records) == 1


def test_a_successful_put_lets_a_degraded_backend_be_read_again(
    settings_restored: None,
):
    backend = publish(BrokenBackend(fail_evict=True))
    calls: list[int] = []
    Row = make_row_class(calls)

    from pyjinhx.reactive.cache import invalidate

    with request_scope():
        invalidate(["rows:7"])
    assert is_degraded(backend) is True

    # This request's write lands, which clears the flag...
    with request_scope():
        Row.load(7)
    assert is_degraded(backend) is False

    # ...so the next one consults the backend again and is served from it.
    backend.gets.clear()
    with request_scope():
        Row.load(7)

    assert backend.gets != []
    assert calls == [7]


def test_two_backends_degrade_independently(settings_restored: None):
    first = BrokenBackend(fail_evict=True)
    second = BrokenBackend()

    from pyjinhx.reactive.cache import invalidate

    publish(first)
    with request_scope():
        invalidate(["rows:7"])

    publish(second)
    with request_scope():
        invalidate(["rows:7"])

    assert is_degraded(first) is True
    assert is_degraded(second) is False
