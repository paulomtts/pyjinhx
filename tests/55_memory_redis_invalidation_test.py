from pyjinhx import CacheScope, LoadCache
from pyjinhx.integrations.redis import MEMORY_REDIS_URL, RedisInvalidationBackend
from pyjinhx.cache import InvalidationHub
from tests.ui.reactive.cached_widget import CachedWidget, load_calls


def _reset():
    LoadCache.clear()
    load_calls["count"] = 0


def test_memory_redis_fanout_evicts_process_cache():
    _reset()
    original_scope = LoadCache.scope()
    try:
        LoadCache.set_scope(CacheScope.PROCESS)
        backend = RedisInvalidationBackend(MEMORY_REDIS_URL)
        InvalidationHub.set_backend(backend)
        InvalidationHub.start_listener()

        CachedWidget.load()
        assert load_calls["count"] == 1
        LoadCache.invalidate({"widgets"})
        load_calls["count"] = 0
        CachedWidget.load()
        assert load_calls["count"] == 1
    finally:
        InvalidationHub.stop_listener()
        InvalidationHub.reset()
        LoadCache.set_scope(original_scope)
