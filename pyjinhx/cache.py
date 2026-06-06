from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .utils import coerce_load_key, coerce_load_key_str, interpolate_reactive_keys

if TYPE_CHECKING:
    from .base import BaseComponent

_lock = threading.Lock()
_cache: dict[tuple[type, str | None], "BaseComponent"] = {}
_reverse: dict[str, set[tuple[type, str | None]]] = {}


def _effective_keys(cls: type[Any], key: str | None) -> set[str]:
    return interpolate_reactive_keys(
        getattr(cls, "_pjx_reacts_to", frozenset()),
        key,
        keyed=getattr(cls, "_pjx_keyed", False),
    )


def install_cached_load(cls: type[Any]) -> None:
    """
    Replace a reactive component's own ``load()`` classmethod with a cache-aware
    wrapper. Singletons call ``load(cls)``; instance-keyed components call
    ``load(cls, key)`` — the wrapper caches by ``(class, key)`` and stamps the key
    onto the result.
    """
    original = cls.__dict__["load"]
    raw_func = original.__func__ if isinstance(original, classmethod) else original

    def _cached_load(inner_cls: type[Any], *args: Any) -> "BaseComponent":
        return _load_through_cache(inner_cls, raw_func, args)

    cls.load = classmethod(_cached_load)


def _with_key(instance: "BaseComponent", key: str | None) -> "BaseComponent":
    instance._pjx_key = key
    return instance


def _load_through_cache(
    cls: type[Any],
    raw_func: Callable[..., "BaseComponent"],
    args: tuple[Any, ...],
) -> "BaseComponent":
    raw_key = args[0] if args else None
    coerced_key = coerce_load_key(raw_key) if raw_key is not None else None
    key = coerce_load_key_str(raw_key) if raw_key is not None else None
    cache_key = (cls, key)

    with _lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        return _with_key(cached.model_copy(), key)

    result = raw_func(cls, coerced_key) if coerced_key is not None else raw_func(cls)
    result = _with_key(result, key)

    if key is not None:
        from .utils import pascal_case_to_kebab_case

        default_id = pascal_case_to_kebab_case(cls.__name__)
        if result.id == default_id:
            result.id = f"{default_id}-{key}"

    with _lock:
        _cache[cache_key] = result
        for k in _effective_keys(cls, key):
            _reverse.setdefault(k, set()).add(cache_key)
    return _with_key(result.model_copy(), key)


def invalidate(dirtied: set[str]) -> None:
    """
    Evict every cached ``load()`` result whose (interpolated) reactive keys intersect
    the dirtied keys. ``invalidate({"todo:42"})`` evicts one row; ``invalidate({"todos"})``
    evicts the collection-tier entries. Per-process only.
    """
    if not dirtied:
        return
    with _lock:
        to_evict: set[tuple[type, str | None]] = set()
        for k in dirtied:
            to_evict |= _reverse.get(k, set())
        for cache_key in to_evict:
            _cache.pop(cache_key, None)
            cls, key = cache_key
            for k in _effective_keys(cls, key):
                bucket = _reverse.get(k)
                if bucket is not None:
                    bucket.discard(cache_key)
                    if not bucket:
                        _reverse.pop(k, None)


def clear() -> None:
    """Drop all cached ``load()`` results and the reverse index. Mainly for tests."""
    with _lock:
        _cache.clear()
        _reverse.clear()
