from typing import ClassVar

from pyjinhx import ReactiveComponent, LoadCache
from tests.ui.reactive.cached_widget import CachedWidget, load_calls


def _reset():
    LoadCache.clear()
    load_calls["count"] = 0


def test_load_result_is_cached():
    _reset()
    a = CachedWidget.load()
    b = CachedWidget.load()
    assert load_calls["count"] == 1  # second call short-circuits the real load()
    assert a.value == 1 and b.value == 1


def test_load_returns_independent_copies():
    _reset()
    a = CachedWidget.load()
    a.id = "mutated"
    a.value = 999
    b = CachedWidget.load()
    assert b.id == "cached-widget"
    assert b.value == 1
    assert load_calls["count"] == 1


def test_invalidate_evicts_matching_dependency():
    _reset()
    first = CachedWidget.load()
    LoadCache.invalidate({"widgets"})
    second = CachedWidget.load()
    assert load_calls["count"] == 2
    assert first.value == 1 and second.value == 2


def test_invalidate_unrelated_key_keeps_cache():
    _reset()
    CachedWidget.load()
    LoadCache.invalidate({"users"})
    CachedWidget.load()
    assert load_calls["count"] == 1


def test_invalidate_empty_set_is_noop():
    _reset()
    CachedWidget.load()
    LoadCache.invalidate(set())
    CachedWidget.load()
    assert load_calls["count"] == 1


def test_invalidate_cleans_reverse_index_across_keys():
    LoadCache.clear()
    calls = {"n": 0}

    class MultiDep(ReactiveComponent):
        n: int = 0
        reacts_to: ClassVar[set[str]] = {"alpha", "beta"}

        @classmethod
        def load(cls):
            calls["n"] += 1
            return cls(id="multi", n=calls["n"])

    MultiDep.load()  # n=1, indexed under alpha & beta
    LoadCache.invalidate({"alpha"})  # evict; must also drop it from the beta bucket
    LoadCache.invalidate({"beta"})  # must not raise on the now-clean bucket
    a = MultiDep.load()  # miss -> n=2
    b = MultiDep.load()  # hit -> still n=2
    assert calls["n"] == 2
    assert a.n == 2 and b.n == 2


def test_invalidate_is_exported():
    from pyjinhx import LoadCache as exported

    assert callable(exported)
