from collections.abc import Callable

from pyjinhx import (
    CacheScope,
    InvalidationBackend,
    invalidate,
    set_invalidation_backend,
    set_load_cache_scope,
    start_invalidation_listener,
    stop_invalidation_listener,
)
from pyjinhx.cache import clear, get_load_cache_scope
from pyjinhx.invalidation import reset_invalidation_state
from tests.ui.reactive.cached_widget import CachedWidget, load_calls


class FakeInvalidationBackend(InvalidationBackend):
    def __init__(self) -> None:
        self.published: list[frozenset[str]] = []
        self.handler: Callable[[frozenset[str]], None] | None = None

    def publish(self, keys: frozenset[str]) -> None:
        self.published.append(keys)

    def start(self, handler: Callable[[frozenset[str]], None]) -> None:
        self.handler = handler

    def stop(self) -> None:
        self.handler = None


def _reset():
    clear()
    load_calls["count"] = 0


def test_invalidate_publishes_under_process_scope():
    _reset()
    original_scope = get_load_cache_scope()
    backend = FakeInvalidationBackend()
    try:
        set_load_cache_scope(CacheScope.PROCESS)
        set_invalidation_backend(backend)
        invalidate({"widgets"})
        assert backend.published == [frozenset({"widgets"})]
    finally:
        reset_invalidation_state()
        set_load_cache_scope(original_scope)


def test_invalidate_propagate_false_does_not_publish():
    _reset()
    original_scope = get_load_cache_scope()
    backend = FakeInvalidationBackend()
    try:
        set_load_cache_scope(CacheScope.PROCESS)
        set_invalidation_backend(backend)
        invalidate({"widgets"}, propagate=False)
        assert backend.published == []
    finally:
        reset_invalidation_state()
        set_load_cache_scope(original_scope)


def test_invalidate_does_not_publish_under_request_scope():
    _reset()
    original_scope = get_load_cache_scope()
    backend = FakeInvalidationBackend()
    try:
        set_load_cache_scope(CacheScope.REQUEST)
        set_invalidation_backend(backend)
        invalidate({"widgets"})
        assert backend.published == []
    finally:
        reset_invalidation_state()
        set_load_cache_scope(original_scope)


def test_remote_invalidation_evicts_process_cache():
    _reset()
    original_scope = get_load_cache_scope()
    backend = FakeInvalidationBackend()
    try:
        set_load_cache_scope(CacheScope.PROCESS)
        set_invalidation_backend(backend)
        start_invalidation_listener()
        CachedWidget.load()
        assert load_calls["count"] == 1
        assert backend.handler is not None
        load_calls["count"] = 0
        backend.handler(frozenset({"widgets"}))
        CachedWidget.load()
        assert load_calls["count"] == 1
    finally:
        stop_invalidation_listener()
        reset_invalidation_state()
        set_load_cache_scope(original_scope)
