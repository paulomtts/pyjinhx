"""The tier-2 cache seam: what a cross-request cache backend must provide.

Tier 1 (``cache.py``) keys entries on ``(cls, key)`` tuples and lives inside one
request. Nothing about that survives a process boundary, so this tier keys on
opaque strings and hands eviction to the backend as tags rather than keeping a
reverse index on the caller's side - a backend behind a socket or a disk file
cannot expose one.

``MISS`` is public because a hit is not "the value is not None": ``None`` is a
value a component's load() may legitimately return and cache, and callers need a
sentinel to tell the two apart. Tier 1 keeps the same distinction private
because its ``cache_has()`` already answers the question.

``InMemoryCacheBackend`` is the reference implementation: it exists so the
protocol is exercisable - by tests, and by an app that wants tier-2 semantics in
a single process - without pulling in a storage dependency.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Protocol, runtime_checkable

MISS = object()
"""Answered by ``get()`` when there is no live entry, as distinct from a cached None."""


@runtime_checkable
class CacheBackend(Protocol):
    """The store a cross-request cache reads through and writes behind.

    Conformance is structural: anything with these four methods is a backend,
    and ``isinstance(x, CacheBackend)`` says so. The protocol declares no
    exceptions - an implementation backed by a disk or a network may raise for
    its own reasons, and handling that is the calling tier's job, not something
    every implementation has to swallow.
    """

    def get(self, key: str) -> object:
        """Return the value stored under ``key``, or ``MISS``.

        A key that was never stored, was evicted, or has outlived its ttl is a
        miss, not an error.
        """
        ...

    def put(
        self, key: str, value: object, *, tags: Iterable[str], ttl: float | None
    ) -> None:
        """Store ``value`` under ``key``, replacing any entry already there.

        Args:
            key: The entry's key; opaque to the backend.
            value: The value to store, as-is.
            tags: Labels ``evict()`` can later match this entry on. A re-put
                replaces the entry's tags outright rather than adding to them.
            ttl: Seconds until the entry becomes a miss, or None to never
                expire on its own.
        """
        ...

    def evict(self, tags: Iterable[str]) -> None:
        """Drop every entry carrying any of these tags.

        Tags that match nothing - including no tags at all - drop nothing,
        which is a no-op rather than an error.
        """
        ...

    def clear(self) -> None:
        """Drop every entry and every tag, whatever its ttl."""
        ...


class InMemoryCacheBackend:
    """A ``CacheBackend`` holding everything in this process's memory.

    Values are stored by reference: nothing is pickled, coerced or copied, so
    what ``get()`` answers is the object ``put()`` was handed.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        """Build an empty backend.

        Args:
            clock: The seconds source ttl deadlines are measured against.
                Injectable so callers that need a different time base - tests
                above all - do not have to wait out real seconds.
        """
        self._clock = clock
        self._entries: dict[str, tuple[object, float | None]] = {}

    def get(self, key: str) -> object:
        """Return the value stored under ``key``, or ``MISS``."""
        entry = self._entries.get(key)
        if entry is None:
            return MISS
        value, _expires_at = entry
        return value

    def put(
        self, key: str, value: object, *, tags: Iterable[str], ttl: float | None
    ) -> None:
        """Store ``value`` under ``key``, replacing any entry already there."""
        self._entries[key] = (value, None)

    def evict(self, tags: Iterable[str]) -> None:
        """Drop every entry carrying any of these tags."""

    def clear(self) -> None:
        """Drop every entry and every tag, whatever its ttl."""
        self._entries.clear()
