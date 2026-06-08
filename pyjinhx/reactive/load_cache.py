from __future__ import annotations

import threading
from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from .keys import (
    coerce_load_key_str,
    coerce_reactive_keys,
    interpolate_reactive_keys,
)

if TYPE_CHECKING:
    from pyjinhx.core.base import BaseComponent


class CacheScope(str, Enum):
    REQUEST = "request"
    PROCESS = "process"
    NONE = "none"


@dataclass
class _CacheState:
    _cache: dict[tuple[type, str | None], BaseComponent] = field(default_factory=dict)
    _reverse: dict[str, set[tuple[type, str | None]]] = field(default_factory=dict)
    _stems: dict[str, set[str]] = field(default_factory=dict)


class LoadCache:
    """Request- and process-scoped memoization for reactive ``load()`` results."""

    _scope: ClassVar[CacheScope] = CacheScope.REQUEST
    _request_cache: ClassVar[ContextVar[_CacheState | None]] = ContextVar(
        "load_cache_request", default=None
    )
    _process_state: ClassVar[_CacheState] = _CacheState()
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def scope(cls) -> CacheScope:
        return cls._scope

    @classmethod
    def set_scope(cls, scope: CacheScope) -> None:
        cls._scope = scope

    @classmethod
    def init_request(cls) -> None:
        """Create a fresh request-scoped cache. Called by ``Registry.request_scope``."""
        cls._request_cache.set(_CacheState())

    @classmethod
    def reset_request(cls) -> None:
        """Drop the request-scoped cache. Called by ``Registry.request_scope``."""
        cls._request_cache.set(None)

    @classmethod
    def clear(cls) -> None:
        """Drop all cached ``load()`` results and reverse indexes. Mainly for tests."""
        with cls._lock:
            cls._process_state._cache.clear()
            cls._process_state._reverse.clear()
            cls._process_state._stems.clear()
            request_store = cls._request_store()
            if request_store is not None:
                request_store._cache.clear()
                request_store._reverse.clear()
                request_store._stems.clear()

    @classmethod
    def invalidate(cls, dirtied: Iterable[object], *, propagate: bool = True) -> None:
        """
        Evict every cached ``load()`` result whose reactive keys intersect ``dirtied``.

        When ``CacheScope.PROCESS`` is active and an ``InvalidationBackend`` is
        configured, ``propagate=True`` publishes keys to other workers after local eviction.
        """
        keys = coerce_reactive_keys(dirtied)
        if not keys:
            return
        cls._evict_local(keys)
        if propagate and cls.scope() == CacheScope.PROCESS:
            from .invalidation import InvalidationHub

            InvalidationHub.publish(frozenset(keys))

    @classmethod
    def install_cached_load(cls, component_class: type[Any]) -> None:
        """
        Replace a reactive component's ``load()`` with a cache-aware wrapper keyed by
        ``(class, instance_key)``.
        """
        original = component_class.__dict__["load"]
        component_class._pjx_raw_load = (
            original.__func__ if isinstance(original, classmethod) else original
        )
        component_class.load = classmethod(cls._cached_load)

    @classmethod
    def _cached_load(
        cls,
        component_class: type[Any],
        *args: Any,
    ) -> BaseComponent:
        raw_func = component_class._pjx_raw_load
        raw_key = args[0] if args else None
        key = coerce_load_key_str(raw_key) if raw_key is not None else None
        cache_key = (component_class, key)

        if cls.scope() != CacheScope.NONE:
            with cls._lock:
                cached = cls._cache_get(cache_key)
            if cached is not None:
                return cls._with_key(cached.model_copy(), key)

        from .context import LoadContext

        ctx = LoadContext.current()
        if key is not None:
            if LoadContext.accepts_ctx(raw_func):
                result = raw_func(component_class, key, ctx=ctx)
            else:
                result = raw_func(component_class, key)
        elif LoadContext.accepts_ctx(raw_func):
            result = raw_func(component_class, ctx=ctx)
        else:
            result = raw_func(component_class)
        result = cls._with_key(result, key)

        from .dev import validate_depends_on

        validate_depends_on(result)

        if key is not None:
            from ..utils import pascal_case_to_kebab_case

            default_id = pascal_case_to_kebab_case(component_class.__name__)
            if result.id == default_id:
                result.id = f"{default_id}-{key}"

        if cls.scope() != CacheScope.NONE:
            with cls._lock:
                cls._cache_put(cache_key, result, component_class, key)
        return cls._with_key(result.model_copy(), key)

    @classmethod
    def _request_store(cls) -> _CacheState | None:
        return cls._request_cache.get()

    @classmethod
    def _active_stores(cls, *, for_invalidate: bool) -> list[_CacheState]:
        if for_invalidate:
            stores: list[_CacheState] = []
            request_store = cls._request_store()
            if request_store is not None:
                stores.append(request_store)
            if cls.scope() == CacheScope.PROCESS:
                stores.append(cls._process_state)
            return stores

        if cls.scope() == CacheScope.NONE:
            return []
        if cls.scope() == CacheScope.PROCESS:
            return [cls._process_state]
        store = cls._request_store()
        return [store] if store is not None else []

    @staticmethod
    def _static_effective_keys(component_class: type[Any], key: str | None) -> set[str]:
        return interpolate_reactive_keys(
            getattr(component_class, "_pjx_reacts_to", frozenset()),
            key,
            keyed=getattr(component_class, "_pjx_keyed", False),
        )

    @classmethod
    def _indexed_keys(cls, instance: BaseComponent) -> set[str]:
        if hasattr(instance, "depends_on"):
            return instance.depends_on()
        return cls._static_effective_keys(
            instance.__class__,
            getattr(instance, "_pjx_key", None),
        )

    @classmethod
    def _unindex_cache_key(
        cls, state: _CacheState, cache_key: tuple[type, str | None]
    ) -> None:
        existing = state._cache.get(cache_key)
        if existing is None:
            return
        for reactive_key in cls._indexed_keys(existing):
            bucket = state._reverse.get(reactive_key)
            if bucket is not None:
                bucket.discard(cache_key)
                if not bucket:
                    state._reverse.pop(reactive_key, None)
            if ":" in reactive_key:
                stem = reactive_key.split(":", 1)[0]
                stem_bucket = state._stems.get(stem)
                if stem_bucket is not None:
                    stem_bucket.discard(reactive_key)
                    if not stem_bucket:
                        state._stems.pop(stem, None)

    @classmethod
    def _evict_from_state(cls, state: _CacheState, keys: set[str]) -> None:
        if not keys:
            return
        to_evict: set[tuple[type, str | None]] = set()
        for key in keys:
            to_evict |= state._reverse.get(key, set())
            if ":" not in key:
                for reverse_key in state._stems.get(key, set()):
                    to_evict |= state._reverse.get(reverse_key, set())
        for cache_key in to_evict:
            cached = state._cache.pop(cache_key, None)
            if cached is None:
                continue
            for reactive_key in cls._indexed_keys(cached):
                bucket = state._reverse.get(reactive_key)
                if bucket is not None:
                    bucket.discard(cache_key)
                    if not bucket:
                        state._reverse.pop(reactive_key, None)
                if ":" in reactive_key:
                    stem = reactive_key.split(":", 1)[0]
                    stem_bucket = state._stems.get(stem)
                    if stem_bucket is not None:
                        stem_bucket.discard(reactive_key)
                        if not stem_bucket:
                            state._stems.pop(stem, None)

    @classmethod
    def _evict_local(cls, keys: set[str]) -> None:
        with cls._lock:
            for state in cls._active_stores(for_invalidate=True):
                cls._evict_from_state(state, keys)

    @staticmethod
    def _with_key(instance: BaseComponent, key: str | None) -> BaseComponent:
        instance._pjx_key = key
        return instance

    @classmethod
    def _cache_get(cls, cache_key: tuple[type, str | None]) -> BaseComponent | None:
        for state in cls._active_stores(for_invalidate=False):
            cached = state._cache.get(cache_key)
            if cached is not None:
                return cached
        return None

    @classmethod
    def _cache_put(
        cls,
        cache_key: tuple[type, str | None],
        result: BaseComponent,
        component_class: type[Any],
        key: str | None,
    ) -> None:
        for state in cls._active_stores(for_invalidate=False):
            cls._unindex_cache_key(state, cache_key)
            state._cache[cache_key] = result
            for reactive_key in cls._indexed_keys(result):
                state._reverse.setdefault(reactive_key, set()).add(cache_key)
                if ":" in reactive_key:
                    stem = reactive_key.split(":", 1)[0]
                    state._stems.setdefault(stem, set()).add(reactive_key)
