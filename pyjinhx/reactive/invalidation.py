from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

logger = logging.getLogger("pyjinhx")

_listener_lock = threading.Lock()
_backend: InvalidationBackend | None = None
_listener_started = False


class InvalidationBackend(ABC):
    """Base class for cross-process load-cache invalidation fan-out."""

    @abstractmethod
    def publish(self, keys: frozenset[str]) -> None: ...

    @abstractmethod
    def start(self, handler: Callable[[frozenset[str]], None]) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


def set_invalidation_backend(backend: InvalidationBackend | None) -> None:
    global _backend
    with _listener_lock:
        if _listener_started and _backend is not None:
            _backend.stop()
        _backend = backend


def publish_invalidation(keys: frozenset[str]) -> None:
    if not keys or _backend is None:
        return
    try:
        _backend.publish(keys)
    except Exception:
        logger.exception("Failed to publish load-cache invalidation for keys %r", keys)


def _on_remote_invalidation(keys: frozenset[str]) -> None:
    from .cache import invalidate

    invalidate(keys, propagate=False)


def start_invalidation_listener() -> None:
    global _listener_started
    with _listener_lock:
        if _backend is None:
            raise RuntimeError(
                "No InvalidationBackend configured; call set_invalidation_backend() first."
            )
        if _listener_started:
            return
        _backend.start(_on_remote_invalidation)
        _listener_started = True


def stop_invalidation_listener() -> None:
    global _listener_started
    with _listener_lock:
        if _backend is None or not _listener_started:
            return
        _backend.stop()
        _listener_started = False


def reset_invalidation_state() -> None:
    """Reset backend listener state. Mainly for tests."""
    global _listener_started, _backend
    with _listener_lock:
        if _listener_started and _backend is not None:
            _backend.stop()
        _listener_started = False
        _backend = None
