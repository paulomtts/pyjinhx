from pyjinhx import (
    CacheScope,
    Registry,
    get_load_cache_scope,
    invalidate,
    set_load_cache_scope,
)
from pyjinhx.cache import clear
from tests.ui.reactive.cached_widget import CachedWidget, load_calls


def _reset():
    clear()
    load_calls["count"] = 0


def test_request_scope_within_request_caches():
    _reset()
    CachedWidget.load()
    CachedWidget.load()
    assert load_calls["count"] == 1


def test_request_scope_invalidate_evicts_within_request():
    _reset()
    first = CachedWidget.load()
    invalidate({"widgets"})
    second = CachedWidget.load()
    assert load_calls["count"] == 2
    assert first.value == 1 and second.value == 2


def test_request_scope_no_cross_request_cache():
    _reset()
    original = get_load_cache_scope()
    try:
        set_load_cache_scope(CacheScope.REQUEST)
        with Registry.request_scope():
            CachedWidget.load()
        with Registry.request_scope():
            CachedWidget.load()
        assert load_calls["count"] == 2
    finally:
        set_load_cache_scope(original)


def test_process_scope_cross_request_cache():
    _reset()
    original = get_load_cache_scope()
    try:
        set_load_cache_scope(CacheScope.PROCESS)
        CachedWidget.load()
        CachedWidget.load()
        assert load_calls["count"] == 1
    finally:
        set_load_cache_scope(original)


def test_none_scope_always_loads():
    _reset()
    original = get_load_cache_scope()
    try:
        set_load_cache_scope(CacheScope.NONE)
        CachedWidget.load()
        CachedWidget.load()
        assert load_calls["count"] == 2
    finally:
        set_load_cache_scope(original)


def test_scope_setter_getter_round_trip():
    original = get_load_cache_scope()
    try:
        set_load_cache_scope(CacheScope.PROCESS)
        assert get_load_cache_scope() == CacheScope.PROCESS
        set_load_cache_scope(CacheScope.NONE)
        assert get_load_cache_scope() == CacheScope.NONE
    finally:
        set_load_cache_scope(original)
