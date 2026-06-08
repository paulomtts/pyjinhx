"""
Reference Redis invalidation backend for multi-worker CacheScope.PROCESS setups.

- ``memory://`` — in-process FakeRedis (``pip install pyjinhx[redis]``), for demos/tests
- ``redis://...`` — real Redis (``pip install pyjinhx[redis]``)
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from pyjinhx.reactive.invalidation import InvalidationBackend

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "pyjinhx:invalidate"
MEMORY_REDIS_URL = "memory://"


def _redis_clients(redis_url: str) -> tuple[Any, Any]:
    """Return separate (publish, subscribe) clients for pub/sub."""
    if redis_url == MEMORY_REDIS_URL or redis_url.startswith("memory://"):
        try:
            import fakeredis
        except ImportError as exc:
            raise ImportError(
                "memory:// requires fakeredis: pip install pyjinhx[redis]"
            ) from exc
        server = fakeredis.FakeServer()
        return (
            fakeredis.FakeRedis(server=server, decode_responses=True),
            fakeredis.FakeRedis(server=server, decode_responses=True),
        )
    try:
        import redis
    except ImportError as exc:
        raise ImportError(
            "Redis URLs require the redis package: pip install pyjinhx[redis]"
        ) from exc
    publish_client = redis.from_url(redis_url, decode_responses=True)
    subscribe_client = redis.from_url(redis_url, decode_responses=True)
    return publish_client, subscribe_client


class RedisInvalidationBackend(InvalidationBackend):
    """Redis pub/sub fan-out for ``invalidate()`` across Gunicorn/Uvicorn workers."""

    def __init__(
        self,
        redis_url: str,
        *,
        channel: str = DEFAULT_CHANNEL,
    ) -> None:
        self._redis_url = redis_url
        self._channel = channel
        self._pub_client: Any = None
        self._sub_client: Any = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._handler: Callable[[frozenset[str]], None] | None = None

    def _ensure_clients(self) -> tuple[Any, Any]:
        if self._pub_client is not None and self._sub_client is not None:
            return self._pub_client, self._sub_client
        self._pub_client, self._sub_client = _redis_clients(self._redis_url)
        return self._pub_client, self._sub_client

    def publish(self, keys: frozenset[str]) -> None:
        if not keys:
            return
        pub_client, _ = self._ensure_clients()
        payload = json.dumps(sorted(keys))
        pub_client.publish(self._channel, payload)

    def start(self, handler: Callable[[frozenset[str]], None]) -> None:
        self._handler = handler
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="pyjinhx-redis-invalidation",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        for client in (self._pub_client, self._sub_client):
            if client is not None:
                try:
                    client.close()
                except Exception:
                    logger.debug("Error closing Redis client", exc_info=True)
        self._pub_client = None
        self._sub_client = None
        self._handler = None

    def _listen_loop(self) -> None:
        _, sub_client = self._ensure_clients()
        pubsub = sub_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(self._channel)
        try:
            while not self._stop_event.is_set():
                message = pubsub.get_message(timeout=1.0)
                if message is None or message.get("type") != "message":
                    continue
                data = message.get("data")
                if not data or self._handler is None:
                    continue
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("Ignoring invalid invalidation payload: %r", data)
                    continue
                if not isinstance(parsed, list):
                    continue
                self._handler(frozenset(str(key) for key in parsed))
        finally:
            try:
                pubsub.unsubscribe(self._channel)
                pubsub.close()
            except Exception:
                logger.debug("Error closing Redis pubsub", exc_info=True)
