from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from ..utils import (
    coerce_load_key_str,
    coerce_reactive_keys,
    interpolate_reactive_keys,
)

if TYPE_CHECKING:
    from pyjinhx.core.base import BaseComponent

_lock = threading.Lock()


class CacheScope(str, Enum):
    REQUEST = "request"
    PROCESS = "process"
    NONE = "none"


_scope: CacheScope = CacheScope.REQUEST
_request_cache: ContextVar[CacheState | None] = ContextVar(
    "load_cache_request", default=None
)


@dataclass
class CacheState:
    _cache: dict[tuple[type, str | None], BaseComponent] = field(default_factory=dict)
    _reverse: dict[str, set[tuple[type, str | None]]] = field(default_factory=dict)


_process_state = CacheState()


def get_load_cache_scope() -> CacheScope:
    return _scope


def set_load_cache_scope(scope: CacheScope) -> None:
    global _scope
    _scope = scope


def init_request_cache() -> None:
    """Create a fresh request-scoped cache. Called by ``Registry.request_scope``."""
    _request_cache.set(CacheState())


def reset_request_cache() -> None:
    """Drop the request-scoped cache. Called by ``Registry.request_scope``."""
    _request_cache.set(None)


def _effective_keys(cls: type[Any], key: str | None) -> set[str]:
    return interpolate_reactive_keys(
        getattr(cls, "_pjx_reacts_to", frozenset()),
        key,
        keyed=getattr(cls, "_pjx_keyed", False),
    )


def _request_store() -> CacheState | None:
    return _request_cache.get()


def _stores_for_read() -> list[CacheState]:
    scope = get_load_cache_scope()
    if scope == CacheScope.NONE:
        return []
    if scope == CacheScope.PROCESS:
        return [_process_state]
    store = _request_store()
    return [store] if store is not None else []


def _stores_for_write() -> list[CacheState]:
    return _stores_for_read()


def _stores_for_invalidate() -> list[CacheState]:
    stores: list[CacheState] = []
    request_store = _request_store()
    if request_store is not None:
        stores.append(request_store)
    if get_load_cache_scope() == CacheScope.PROCESS:
        stores.append(_process_state)
    return stores


def _evict_from_state(state: CacheState, keys: set[str]) -> None:
    if not keys:
        return
    to_evict: set[tuple[type, str | None]] = set()
    for key in keys:
        to_evict |= state._reverse.get(key, set())
        if ":" not in key:
            instance_prefix = f"{key}:"
            for reverse_key, cache_keys in state._reverse.items():
                if reverse_key.startswith(instance_prefix):
                    to_evict |= cache_keys
    for cache_key in to_evict:
        state._cache.pop(cache_key, None)
        cls, load_key = cache_key
        for reactive_key in _effective_keys(cls, load_key):
            bucket = state._reverse.get(reactive_key)
            if bucket is not None:
                bucket.discard(cache_key)
                if not bucket:
                    state._reverse.pop(reactive_key, None)


def _evict_local(keys: set[str]) -> None:
    with _lock:
        for state in _stores_for_invalidate():
            _evict_from_state(state, keys)


def install_cached_load(cls: type[Any]) -> None:
    """
    Replace a reactive component's own ``load()`` classmethod with a cache-aware
    wrapper. Singletons call ``load(cls)``; instance-keyed components call
    ``load(cls, key)`` — the wrapper caches by ``(class, key)`` and stamps the key
    onto the result.
    """
    original = cls.__dict__["load"]
    raw_func = original.__func__ if isinstance(original, classmethod) else original

    def _cached_load(inner_cls: type[Any], *args: Any) -> BaseComponent:
        return _load_through_cache(inner_cls, raw_func, args)

    cls.load = classmethod(_cached_load)


def _with_key(instance: BaseComponent, key: str | None) -> BaseComponent:
    instance._pjx_key = key
    return instance


def _cache_get(cache_key: tuple[type, str | None]) -> BaseComponent | None:
    for state in _stores_for_read():
        cached = state._cache.get(cache_key)
        if cached is not None:
            return cached
    return None


def _cache_put(
    cache_key: tuple[type, str | None],
    result: BaseComponent,
    cls: type[Any],
    key: str | None,
) -> None:
    for state in _stores_for_write():
        state._cache[cache_key] = result
        for reactive_key in _effective_keys(cls, key):
            state._reverse.setdefault(reactive_key, set()).add(cache_key)


def _load_through_cache(
    cls: type[Any],
    raw_func: Callable[..., BaseComponent],
    args: tuple[Any, ...],
) -> BaseComponent:
    raw_key = args[0] if args else None
    key = coerce_load_key_str(raw_key) if raw_key is not None else None
    cache_key = (cls, key)

    if get_load_cache_scope() != CacheScope.NONE:
        with _lock:
            cached = _cache_get(cache_key)
        if cached is not None:
            return _with_key(cached.model_copy(), key)

    from .context import get_load_context, load_accepts_ctx
    from .dev import validate_load_reads

    ctx = get_load_context()
    if key is not None:
        if load_accepts_ctx(raw_func):
            result = raw_func(cls, key, ctx=ctx)
        else:
            result = raw_func(cls, key)
    elif load_accepts_ctx(raw_func):
        result = raw_func(cls, ctx=ctx)
    else:
        result = raw_func(cls)
    result = _with_key(result, key)

    validate_load_reads(
        cls,
        declared_reads=set(getattr(cls, "_pjx_load_reads", frozenset())),
        reacts_to=set(getattr(cls, "_pjx_reacts_to", frozenset())),
    )

    if key is not None:
        from ..utils import pascal_case_to_kebab_case

        default_id = pascal_case_to_kebab_case(cls.__name__)
        if result.id == default_id:
            result.id = f"{default_id}-{key}"

    if get_load_cache_scope() != CacheScope.NONE:
        with _lock:
            _cache_put(cache_key, result, cls, key)
    return _with_key(result.model_copy(), key)


def invalidate(dirtied: Iterable[object], *, propagate: bool = True) -> None:
    """
    Evict every cached ``load()`` result whose (interpolated) reactive keys intersect
    the dirtied keys. ``invalidate({"todo:42"})`` evicts one row; ``invalidate({"todos"})``
    evicts the collection-tier entries.

    When ``CacheScope.PROCESS`` is active and an ``InvalidationBackend`` is configured,
    ``propagate=True`` (default) publishes the dirtied keys to other workers after local
    eviction.
    """
    keys = coerce_reactive_keys(dirtied)
    if not keys:
        return
    _evict_local(keys)
    if propagate and get_load_cache_scope() == CacheScope.PROCESS:
        from .invalidation import publish_invalidation

        publish_invalidation(frozenset(keys))


def clear() -> None:
    """Drop all cached ``load()`` results and reverse indexes. Mainly for tests."""
    with _lock:
        _process_state._cache.clear()
        _process_state._reverse.clear()
        request_store = _request_store()
        if request_store is not None:
            request_store._cache.clear()
            request_store._reverse.clear()
