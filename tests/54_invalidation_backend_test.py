from collections.abc import Callable

from pyjinhx import CacheScope, InvalidationBackend, InvalidationHub, LoadCache


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
    LoadCache.clear()


def test_invalidate_publishes_under_process_scope():
    _reset()
    original_scope = LoadCache.scope()
    backend = FakeInvalidationBackend()
    try:
        LoadCache.set_scope(CacheScope.PROCESS)
        InvalidationHub.set_backend(backend)
        LoadCache.invalidate({"widgets"})
        assert backend.published == [frozenset({"widgets"})]
    finally:
        InvalidationHub.reset()
        LoadCache.set_scope(original_scope)


def test_invalidate_propagate_false_does_not_publish():
    _reset()
    original_scope = LoadCache.scope()
    backend = FakeInvalidationBackend()
    try:
        LoadCache.set_scope(CacheScope.PROCESS)
        InvalidationHub.set_backend(backend)
        LoadCache.invalidate({"widgets"}, propagate=False)
        assert backend.published == []
    finally:
        InvalidationHub.reset()
        LoadCache.set_scope(original_scope)


def test_remote_invalidation_evicts_process_cache():
    from tests.ui.reactive.cached_widget import CachedWidget, load_calls

    _reset()
    load_calls["count"] = 0
    original_scope = LoadCache.scope()
    backend = FakeInvalidationBackend()
    try:
        LoadCache.set_scope(CacheScope.PROCESS)
        InvalidationHub.set_backend(backend)
        InvalidationHub.start_listener()
        CachedWidget.load()
        assert load_calls["count"] == 1
        assert backend.handler is not None
        load_calls["count"] = 0
        backend.handler(frozenset({"widgets"}))
        CachedWidget.load()
        assert load_calls["count"] == 1
    finally:
        InvalidationHub.stop_listener()
        InvalidationHub.reset()
        LoadCache.set_scope(original_scope)


def test_listener_restarts_after_backend_swap():
    original_scope = LoadCache.scope()
    first = FakeInvalidationBackend()
    second = FakeInvalidationBackend()
    try:
        LoadCache.set_scope(CacheScope.PROCESS)
        InvalidationHub.set_backend(first)
        InvalidationHub.start_listener()
        assert first.handler is not None

        InvalidationHub.set_backend(second)
        InvalidationHub.start_listener()
        assert first.handler is None
        assert second.handler is not None
    finally:
        InvalidationHub.stop_listener()
        InvalidationHub.reset()
        LoadCache.set_scope(original_scope)
