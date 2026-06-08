from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

logger = logging.getLogger("pyjinhx")


class InvalidationBackend(ABC):
    """Base class for cross-process load-cache invalidation fan-out."""

    @abstractmethod
    def publish(self, keys: frozenset[str]) -> None: ...

    @abstractmethod
    def start(self, handler: Callable[[frozenset[str]], None]) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


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
        from .load_cache import LoadCache

        LoadCache.invalidate(keys, propagate=False)
