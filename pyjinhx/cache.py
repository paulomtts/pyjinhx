from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseComponent

_lock = threading.Lock()
_cache: dict[type, "BaseComponent"] = {}
_reverse: dict[str, set[type]] = {}


def install_cached_load(cls: type) -> None:
    """
    Replace a reactive component's own ``load()`` classmethod with a cache-aware
    wrapper. Called from ``BaseComponent.__init_subclass__`` for every reactive
    subclass that defines its own ``load``.
    """
    original = cls.__dict__["load"]
    raw_func = original.__func__ if isinstance(original, classmethod) else original

    def _cached_load(inner_cls):
        return _load_through_cache(inner_cls, raw_func)

    cls.load = classmethod(_cached_load)


def _load_through_cache(cls, raw_func):
    with _lock:
        cached = _cache.get(cls)
    if cached is not None:
        return cached.model_copy()

    # Run the real load() (the DB hit) OUTSIDE the lock.
    result = raw_func(cls)

    with _lock:
        _cache[cls] = result
        for key in getattr(cls, "_pjx_depends_on", frozenset()):
            _reverse.setdefault(key, set()).add(cls)
    return result.model_copy()


def invalidate(dirtied: set[str]) -> None:
    """
    Evict every cached ``load()`` result whose component depends on a dirtied key.

    Reactive ``render(dirtied=...)`` / ``oob_swaps`` call this automatically; call
    it yourself for mutations that happen outside a render (e.g. a background job).
    Per-process only — multi-worker coherence is the application's responsibility.
    """
    if not dirtied:
        return
    with _lock:
        to_evict: set[type] = set()
        for key in dirtied:
            to_evict |= _reverse.get(key, set())
        for cls in to_evict:
            _cache.pop(cls, None)
            for key in getattr(cls, "_pjx_depends_on", frozenset()):
                bucket = _reverse.get(key)
                if bucket is not None:
                    bucket.discard(cls)
                    if not bucket:
                        _reverse.pop(key, None)


def clear() -> None:
    """Drop all cached ``load()`` results and the reverse index. Mainly for tests."""
    with _lock:
        _cache.clear()
        _reverse.clear()
