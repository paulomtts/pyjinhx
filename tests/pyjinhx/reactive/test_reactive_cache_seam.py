"""The cascade itself: which tier answered a load(), seen from the backend's side.

test_reactive_cache_tier2_wiring.py proves each tier's plumbing works. This file
proves the order they are consulted in, by recording every call wrapped_load
makes to the backend and asserting on that ledger: a tier-1 hit must produce no
backend traffic at all, and the ttl a class resolves to must be the ttl that
actually reaches put(), not merely the one _resolve_tier2 reports.
"""

from collections.abc import Iterable
from typing import Annotated

import pytest

from pyjinhx.config import configure_pyjinhx, current_settings
from pyjinhx.reactive.backend import MISS, CachePolicy, InMemoryCacheBackend
from pyjinhx.reactive.cache import cache_has, invalidate
from pyjinhx.reactive.component import (
    PjxKey,
    ReactiveComponent,
    _cache_key,
    _string_cache_key,
)
from pyjinhx.session import request_scope


class LedgerBackend(InMemoryCacheBackend):
    """An in-memory backend that records every call with its full arguments.

    put() is recorded with its tags and ttl, not just its key: the ttl a class
    resolves to is only observable here, at the call the seam actually makes.
    """

    def __init__(self) -> None:
        super().__init__()
        self.gets: list[str] = []
        self.puts: list[tuple[str, object, tuple[str, ...], float | None]] = []
        self.evicts: list[tuple[str, ...]] = []

    def get(self, key: str) -> object:
        self.gets.append(key)
        return super().get(key)

    def put(
        self, key: str, value: object, *, tags: Iterable[str], ttl: float | None
    ) -> None:
        collected = tuple(tags)
        self.puts.append((key, value, collected, ttl))
        super().put(key, value, tags=collected, ttl=ttl)

    def evict(self, tags: Iterable[str]) -> None:
        collected = tuple(tags)
        self.evicts.append(collected)
        super().evict(collected)


@pytest.fixture
def ledger():
    """Publish a fresh LedgerBackend for one test, then restore the settings.

    configure_pyjinhx rather than shutdown_pyjinhx: the latter resets every
    other setting too, and a test that only asked for a backend should not also
    blow away whatever else the process was configured with.
    """
    previous = current_settings()
    published = LedgerBackend()
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


def test_the_ledger_backend_records_a_put_with_its_tags_and_ttl():
    """The fake itself is load-bearing, so its recording is asserted directly."""
    backend = LedgerBackend()

    backend.put("k", "v", tags=("rows", "rows:7"), ttl=45)

    assert backend.puts == [("k", "v", ("rows", "rows:7"), 45)]
    assert backend.get("k") == "v"
    assert backend.gets == ["k"]
