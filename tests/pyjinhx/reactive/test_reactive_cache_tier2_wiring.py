"""The two-tier seam: wrapped_load reading/writing tier 2, invalidate evicting it."""

from typing import Annotated

import pytest

from pyjinhx.config import PjxSettings, configure_pyjinhx, current_settings
from pyjinhx.reactive.backend import CachePolicy, InMemoryCacheBackend
from pyjinhx.reactive.component import (
    PjxKey,
    ReactiveComponent,
    _resolve_tier2,
)


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
