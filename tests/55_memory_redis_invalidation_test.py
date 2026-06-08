from pyjinhx import CacheScope, invalidate, set_invalidation_backend, set_load_cache_scope
from pyjinhx.reactive.cache import clear, get_load_cache_scope
from pyjinhx.reactive.invalidation import reset_invalidation_state, start_invalidation_listener, stop_invalidation_listener
from pyjinhx.integrations.redis import MEMORY_REDIS_URL, RedisInvalidationBackend
from tests.ui.reactive.cached_widget import CachedWidget, load_calls


def _reset():
    clear()
    load_calls["count"] = 0


def test_memory_redis_fanout_evicts_process_cache():
    _reset()
    original_scope = get_load_cache_scope()
    try:
        set_load_cache_scope(CacheScope.PROCESS)
        backend = RedisInvalidationBackend(MEMORY_REDIS_URL)
        set_invalidation_backend(backend)
        start_invalidation_listener()

        CachedWidget.load()
        assert load_calls["count"] == 1
        invalidate({"widgets"})
        load_calls["count"] = 0
        CachedWidget.load()
        assert load_calls["count"] == 1
    finally:
        stop_invalidation_listener()
        reset_invalidation_state()
        set_load_cache_scope(original_scope)
