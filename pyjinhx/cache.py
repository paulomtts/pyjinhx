"""Load-cache memoization for ``load()`` and cross-process invalidation."""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from .keys import coerce_load_key_str, coerce_reactive_keys

if TYPE_CHECKING:
    from pyjinhx.base import BaseComponent

logger = logging.getLogger("pyjinhx")


class CacheScope(str, Enum):
    REQUEST = "request"
    PROCESS = "process"
    NONE = "none"


@dataclass
class _CacheState:
    _cache: dict[tuple[type, str | None], BaseComponent] = field(default_factory=dict)
    _reverse: dict[str, set[tuple[type, str | None]]] = field(default_factory=dict)


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
            request_store = cls._request_store()
            if request_store is not None:
                request_store._cache.clear()
                request_store._reverse.clear()

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
            InvalidationHub.publish(frozenset(keys))

    @classmethod
    def install_cached_load(cls, component_class: type[Any]) -> None:
        """
        Replace a reactive component's ``load()`` with a cache-aware wrapper keyed by
        ``(class, load_arg)``.
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

        from .context import PjxContext, invoke_raw_load

        result = invoke_raw_load(
            raw_func,
            component_class,
            key=key,
            ctx=PjxContext.current(),
            owner=component_class,
        )
        result = cls._with_key(result, key)

        if key is not None:
            from .utils import pascal_case_to_kebab_case

            default_id = pascal_case_to_kebab_case(component_class.__name__)
            if result.id == default_id and getattr(result, "_pjx_id_defaulted", True):
                result.id = f"{default_id}-{key}"

        if cls.scope() != CacheScope.NONE:
            with cls._lock:
                cls._cache_put(cache_key, result)
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

    @classmethod
    def _indexed_keys(cls, instance: BaseComponent) -> set[str]:
        from .reactive import ReactiveComponent, _keyed_derived_keys

        if isinstance(instance, ReactiveComponent):
            static = frozenset(getattr(type(instance), "_pjx_reacts_to", frozenset()))
            return set(static) | _keyed_derived_keys(static, instance._pjx_key)
        return set(getattr(instance.__class__, "_pjx_reacts_to", frozenset()))

    @classmethod
    def _drop_reverse(
        cls,
        state: _CacheState,
        cache_key: tuple[type, str | None],
        instance: BaseComponent,
    ) -> None:
        for reactive_key in cls._indexed_keys(instance):
            bucket = state._reverse.get(reactive_key)
            if bucket is not None:
                bucket.discard(cache_key)
                if not bucket:
                    state._reverse.pop(reactive_key, None)

    @classmethod
    def _unindex_cache_key(
        cls, state: _CacheState, cache_key: tuple[type, str | None]
    ) -> None:
        existing = state._cache.get(cache_key)
        if existing is not None:
            cls._drop_reverse(state, cache_key, existing)

    @classmethod
    def _evict_from_state(cls, state: _CacheState, keys: set[str]) -> None:
        if not keys:
            return
        to_evict: set[tuple[type, str | None]] = set()
        for key in keys:
            to_evict |= state._reverse.get(key, set())
        for cache_key in to_evict:
            cached = state._cache.pop(cache_key, None)
            if cached is not None:
                cls._drop_reverse(state, cache_key, cached)

    @classmethod
    def _evict_local(cls, keys: set[str]) -> None:
        with cls._lock:
            for state in cls._active_stores(for_invalidate=True):
                cls._evict_from_state(state, keys)

    @staticmethod
    def _with_key(instance: BaseComponent, key: str | None) -> BaseComponent:
        from .reactive import ReactiveComponent

        if isinstance(instance, ReactiveComponent):
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
    ) -> None:
        for state in cls._active_stores(for_invalidate=False):
            cls._unindex_cache_key(state, cache_key)
            state._cache[cache_key] = result
            for reactive_key in cls._indexed_keys(result):
                state._reverse.setdefault(reactive_key, set()).add(cache_key)


class InvalidationBackend(ABC):
    """Base class for cross-process load-cache invalidation fan-out."""

    DEFAULT_CHANNEL: ClassVar[str] = "pyjinhx:invalidate"

    @abstractmethod
    def publish(self, keys: frozenset[str]) -> None: ...

    @abstractmethod
    def start(self, handler: Callable[[frozenset[str]], None]) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    def _decode_keys(self, raw: str) -> frozenset[str] | None:
        """Parse a published payload into invalidation keys, or None if malformed.

        Shared by every backend's listen/poll loop: a JSON array of keys becomes
        a ``frozenset[str]``; malformed JSON is logged and dropped; a non-list
        payload is silently ignored.
        """
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid invalidation payload: %r", raw)
            return None
        if not isinstance(parsed, list):
            return None
        return frozenset(str(key) for key in parsed)


class InvalidationHub:
    """Runtime coordinator for cross-process load-cache invalidation."""

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _backend: ClassVar[InvalidationBackend | None] = None
    _listener_started: ClassVar[bool] = False

    @classmethod
    def set_backend(cls, backend: InvalidationBackend | None) -> None:
        with cls._lock:
            if cls._listener_started and cls._backend is not None:
                cls._backend.stop()
                cls._listener_started = False
            cls._backend = backend

    @classmethod
    def publish(cls, keys: frozenset[str]) -> None:
        if not keys or cls._backend is None:
            return
        try:
            cls._backend.publish(keys)
        except Exception:
            logger.exception(
                "Failed to publish load-cache invalidation for keys %r", keys
            )

    @classmethod
    def start_listener(cls) -> None:
        with cls._lock:
            if cls._backend is None:
                raise RuntimeError(
                    "No InvalidationBackend configured; call "
                    "InvalidationHub.set_backend() first."
                )
            if cls._listener_started:
                return
            cls._backend.start(cls._on_remote_invalidation)
            cls._listener_started = True

    @classmethod
    def stop_listener(cls) -> None:
        with cls._lock:
            if cls._backend is None or not cls._listener_started:
                return
            cls._backend.stop()
            cls._listener_started = False

    @classmethod
    def reset(cls) -> None:
        """Reset backend listener state. Mainly for tests."""
        with cls._lock:
            if cls._listener_started and cls._backend is not None:
                cls._backend.stop()
            cls._listener_started = False
            cls._backend = None

    @staticmethod
    def _on_remote_invalidation(keys: frozenset[str]) -> None:
        LoadCache.invalidate(keys, propagate=False)
