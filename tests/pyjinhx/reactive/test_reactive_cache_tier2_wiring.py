"""The two-tier seam: wrapped_load reading/writing tier 2, invalidate evicting it."""

from typing import Annotated

import pytest

from pyjinhx.config import configure_pyjinhx, current_settings
from pyjinhx.reactive.backend import MISS, CachePolicy, InMemoryCacheBackend
from pyjinhx.reactive.cache import cache_get, cache_has, invalidate
from pyjinhx.reactive.component import (
    PjxKey,
    ReactiveComponent,
    _cache_key,
    _resolve_tier2,
    _string_cache_key,
)
from pyjinhx.session import add_dirtied, get_cache_forward, get_dirtied, request_scope


@pytest.fixture
def backend():
    """Publish a fresh in-memory backend for one test, then restore the settings.

    configure_pyjinhx rather than shutdown_pyjinhx: the latter resets every
    other setting too, and a test that only asked for a backend should not
    also blow away whatever else the process was configured with.
    """
    previous = current_settings()
    published = InMemoryCacheBackend()
    configure_pyjinhx(previous.merge(cache_backend=published))
    yield published
    configure_pyjinhx(previous)


@pytest.fixture
def no_backend():
    """Publish settings with no cache backend for one test, then restore."""
    previous = current_settings()
    configure_pyjinhx(previous.merge(cache_backend=None))
    yield
    configure_pyjinhx(previous)


def test_resolve_tier2_is_off_when_no_backend_is_configured(no_backend: None):
    class Widget(ReactiveComponent):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            return cls(value="loaded")

    assert _resolve_tier2(Widget) == (None, None)


def test_resolve_tier2_is_on_by_default_at_the_process_default_ttl(
    backend: InMemoryCacheBackend,
):
    class Widget(ReactiveComponent):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            return cls(value="loaded")

    resolved, ttl = _resolve_tier2(Widget)

    assert resolved is backend
    assert ttl == CachePolicy().ttl == 300


def test_resolve_tier2_honors_an_explicit_policy_ttl(backend: InMemoryCacheBackend):
    class Widget(ReactiveComponent, cache=CachePolicy(ttl=45)):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            return cls(value="loaded")

    assert _resolve_tier2(Widget) == (backend, 45)


def test_resolve_tier2_honors_a_never_expiring_policy(backend: InMemoryCacheBackend):
    class Widget(ReactiveComponent, cache=CachePolicy(ttl=None)):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            return cls(value="loaded")

    assert _resolve_tier2(Widget) == (backend, None)


def test_resolve_tier2_is_off_for_a_class_that_opted_out(
    backend: InMemoryCacheBackend,
):
    class Widget(ReactiveComponent, cache=False):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            return cls(value="loaded")

    assert _resolve_tier2(Widget) == (None, None)


def test_resolve_tier2_reads_the_settings_at_call_time(
    backend: InMemoryCacheBackend,
):
    """The backend is looked up per call, not captured when the class is defined."""

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    assert _resolve_tier2(Row)[0] is backend

    replacement = InMemoryCacheBackend()
    configure_pyjinhx(current_settings().merge(cache_backend=replacement))

    assert _resolve_tier2(Row)[0] is replacement


class RecordingBackend(InMemoryCacheBackend):
    """An in-memory backend that remembers which methods it was asked for."""

    def __init__(self) -> None:
        super().__init__()
        self.gets: list[str] = []
        self.puts: list[str] = []
        self.evicts: list[tuple[str, ...]] = []

    def get(self, key: str) -> object:
        self.gets.append(key)
        return super().get(key)

    def put(self, key: str, value: object, *, tags, ttl) -> None:
        self.puts.append(key)
        super().put(key, value, tags=tags, ttl=ttl)

    def evict(self, tags) -> None:
        self.evicts.append(tuple(tags))
        super().evict(self.evicts[-1])


@pytest.fixture
def recording_backend():
    """Publish a RecordingBackend for one test, then restore the settings."""
    previous = current_settings()
    published = RecordingBackend()
    configure_pyjinhx(previous.merge(cache_backend=published))
    yield published
    configure_pyjinhx(previous)


def test_a_miss_writes_through_to_both_tiers(backend: InMemoryCacheBackend):
    calls: list[int] = []

    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        loaded = Row.load(7)

        assert calls == [7]
        assert cache_has(Row, _cache_key(Row, {"row_id": 7}, protocol_mode=False))
        assert (
            cache_get(Row, _cache_key(Row, {"row_id": 7}, protocol_mode=False))
            is loaded
        )

    stored = backend.get(_string_cache_key(Row, {"row_id": 7}, protocol_mode=False))
    assert stored is loaded


def test_a_tier2_hit_is_promoted_into_tier1_and_skips_the_real_load(
    backend: InMemoryCacheBackend,
):
    calls: list[int] = []

    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        first = Row.load(7)

    # A fresh request: tier 1 is empty again, so only tier 2 can answer.
    with request_scope():
        key = _cache_key(Row, {"row_id": 7}, protocol_mode=False)
        assert cache_has(Row, key) is False

        second = Row.load(7)

        assert second is first
        assert calls == [7]
        # Promotion, not a bare return: the rest of this request answers from
        # the dict without consulting the backend again.
        assert cache_has(Row, key) is True
        assert cache_get(Row, key) is first


def test_the_promoted_entry_carries_the_same_reactive_keys(
    backend: InMemoryCacheBackend,
):
    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)

    with request_scope():
        promoted = Row.load(7)
        key = _cache_key(Row, {"row_id": 7}, protocol_mode=False)

        assert get_cache_forward()[(Row, key)] == {"rows", "rows:7"}

        # And the keys actually bite: dirtying the composite drops the promoted
        # entry from tier 1.
        invalidate(["rows:7"])
        assert cache_has(Row, key) is False
        assert promoted is not None


def test_tier2_is_tagged_with_the_same_reactive_keys_tier1_indexes_on(
    recording_backend: RecordingBackend,
):
    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)

    string_key = _string_cache_key(Row, {"row_id": 7}, protocol_mode=False)
    assert recording_backend.puts == [string_key]

    recording_backend.evict(["rows:7"])
    assert recording_backend.get(string_key) is MISS


def test_a_cache_false_class_never_touches_the_backend(
    recording_backend: RecordingBackend,
):
    calls: list[int] = []

    class Row(ReactiveComponent, react=("rows",), cache=False):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)
        Row.load(7)

    with request_scope():
        Row.load(7)

    assert recording_backend.gets == []
    assert recording_backend.puts == []
    # Tier 1 still memoizes within a request, and still starts empty in the next.
    assert calls == [7, 7]


def test_with_no_backend_every_request_runs_the_real_load_once(no_backend: None):
    calls: list[int] = []

    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)
        Row.load(7)

    with request_scope():
        Row.load(7)

    assert calls == [7, 7]


def test_an_expired_tier2_entry_falls_through_to_the_real_load(
    backend: InMemoryCacheBackend,
):
    """ttl is honored per class: a policy that has run out is an ordinary miss."""
    calls: list[int] = []

    class Row(ReactiveComponent, cache=CachePolicy(ttl=0)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)

    with request_scope():
        Row.load(7)

    assert calls == [7, 7]


def test_invalidate_evicts_the_backend_entry_too(backend: InMemoryCacheBackend):
    calls: list[int] = []

    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)

    string_key = _string_cache_key(Row, {"row_id": 7}, protocol_mode=False)
    assert backend.get(string_key) is not MISS

    with request_scope():
        invalidate(["rows:7"])

    assert backend.get(string_key) is MISS

    # The next request has to load for real: neither tier holds it any more.
    with request_scope():
        Row.load(7)

    assert calls == [7, 7]


def test_invalidate_hands_the_backend_the_dirtied_keys_verbatim(
    recording_backend: RecordingBackend,
):
    with request_scope():
        invalidate(["rows", "rows:7"])

    assert recording_backend.evicts == [("rows", "rows:7")]


def test_invalidate_survives_a_one_shot_iterator_of_dirtied_keys(
    recording_backend: RecordingBackend,
):
    """Both tiers see the same keys: the first walk must not drain the second."""

    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)
        key = _cache_key(Row, {"row_id": 7}, protocol_mode=False)

        invalidate(iter(["rows:7"]))

        assert cache_has(Row, key) is False

    assert recording_backend.evicts == [("rows:7",)]
    assert (
        recording_backend.get(
            _string_cache_key(Row, {"row_id": 7}, protocol_mode=False)
        )
        is MISS
    )


def test_invalidate_with_no_backend_configured_is_a_tier1_only_no_op(
    no_backend: None,
):
    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)
        key = _cache_key(Row, {"row_id": 7}, protocol_mode=False)

        invalidate(["rows:7"])

        assert cache_has(Row, key) is False


def test_a_dirtied_key_recorded_through_the_session_clears_both_tiers(
    backend: InMemoryCacheBackend,
):
    """The real path: a mutation records a key, the response fan-out invalidates
    it, and the next request must not be served stale from tier 2."""
    calls: list[int] = []

    class Row(ReactiveComponent, react=("rows",)):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        Row.load(7)

    with request_scope():
        add_dirtied({"rows:7"})
        invalidate(get_dirtied())

    # Both tiers are clear right after invalidate() - before the next request
    # writes a fresh entry back.
    assert (
        backend.get(_string_cache_key(Row, {"row_id": 7}, protocol_mode=False)) is MISS
    )

    with request_scope():
        Row.load(7)

    assert calls == [7, 7]
