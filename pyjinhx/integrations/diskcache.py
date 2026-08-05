"""The disk-backed tier-2 cache: a CacheBackend over diskcache's FanoutCache.

Reached only by a caller that imports it, which is why ``diskcache`` is imported
outright rather than guarded - the same convention as the Starlette import in
``integrations/fastapi.py``. Nothing in ``pyjinhx`` imports this module eagerly,
so installing the extra stays optional.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

from diskcache import FanoutCache

from pyjinhx.reactive.backend import MISS

_KEYS_OF_TAG = "pjx:diskcache:keys-of-tag:"
"""Prefix of the entry holding the set of keys carrying one tag."""

_TAGS_OF_KEY = "pjx:diskcache:tags-of-key:"
"""Prefix of the entry holding the set of tags one key sits under."""


class DiskCacheBackend:
    """A ``CacheBackend`` storing entries in a SQLite-backed directory.

    Entries survive process restarts and are shared by every worker on the
    machine, which is the whole point: N gunicorn workers stop each paying for
    the same load(). It is a one-machine cache, not a one-cluster one - two
    hosts pointed at their own directories hold two independent caches, and an
    eviction on one is invisible to the other.

    ``directory`` must live on local disk. SQLite's locking is unreliable over
    NFS and other network filesystems, and a cache that corrupts under
    concurrency is worse than no cache; this is documented rather than detected
    because the check would be a guess about a mount point.

    Values are pickled on the way in, so what ``get()`` answers is a copy of
    what ``put()`` was handed rather than the same object.

    Tag membership is kept as entries of the cache's own, under reserved
    ``pjx:diskcache:`` key prefixes, rather than diskcache's native one-tag
    ``tag=`` field: an entry may carry several tags, and an index held in this
    process would be invisible to the worker that evicts next.
    """

    def __init__(
        self,
        directory: str | Path,
        *,
        shards: int = 8,
        timeout: float = 0.010,
    ) -> None:
        """Open (or create) a cache under ``directory``.

        Args:
            directory: Where the cache's SQLite shards live. Local disk only.
            shards: How many SQLite databases the entries are spread over.
                More than one because a single database serializes every
                worker behind its write lock.
            timeout: Seconds a shard operation waits on the write lock before
                giving up on that operation.
        """
        self._cache = FanoutCache(str(directory), shards=shards, timeout=timeout)

    def get(self, key: str) -> object:
        """Return the value stored under ``key``, or ``MISS``."""
        # diskcache's own default is None, which a cached None is
        # indistinguishable from; MISS is what the protocol's callers branch on.
        return self._cache.get(key, default=MISS)

    def put(
        self, key: str, value: object, *, tags: Iterable[str], ttl: float | None
    ) -> None:
        """Store ``value`` under ``key``, replacing any entry already there."""
        self._cache.set(key, value, expire=ttl)
        # A replacement may hang off different tags than the entry it replaces,
        # so its old memberships go before the new ones land - merging them
        # would leave the new value evictable by a tag it never claimed.
        self._unindex(key)
        self._index(key, tags)

    def evict(self, tags: Iterable[str]) -> None:
        """Drop every entry carrying any of these tags."""
        doomed: set[str] = set()
        for tag in tags:
            doomed |= self._keys_of(tag)
        # A set, so a key reachable from two of the given tags is deleted once.
        for key in doomed:
            self._cache.delete(key)
            # Un-index every tag the entry sat under, not just the matched ones:
            # the entry is gone, so a surviving membership would name a key
            # nothing can look up.
            self._unindex(key)

    def clear(self) -> None:
        """Drop every entry and every tag, whatever its ttl."""
        self._cache.clear()

    def close(self) -> None:
        """Release the SQLite connections this cache holds open.

        Not part of ``CacheBackend`` - ``shutdown_pyjinhx()`` looks for it by
        name on whatever backend is configured.
        """
        self._cache.close()

    def _index(self, key: str, tags: Iterable[str]) -> None:
        """Record ``key`` as carrying every one of ``tags``."""
        # diskcache's native tag= is one tag per entry, which the protocol's
        # Iterable[str] does not fit, so the index is entries of its own. They
        # live in the cache rather than in a dict on self because the whole
        # point of this backend is that another worker's evict() finds them.
        carried = frozenset(tags)
        if not carried:
            return
        self._cache.set(_TAGS_OF_KEY + key, carried)
        for tag in carried:
            self._cache.set(_KEYS_OF_TAG + tag, self._keys_of(tag) | {key})

    def _unindex(self, key: str) -> None:
        """Remove ``key`` from every tag bucket holding it."""
        # The forward index names exactly the buckets this key sits in, so the
        # cost is the entry's own tag count rather than the whole tag index.
        for tag in self._tags_of(key):
            self._cache.set(_KEYS_OF_TAG + tag, self._keys_of(tag) - {key})
        self._cache.delete(_TAGS_OF_KEY + key)

    def _keys_of(self, tag: str) -> frozenset[str]:
        """Every key currently recorded under ``tag``."""
        # self._cache.get() is untyped in diskcache and its inferred return
        # includes types (bytes, a BufferedReader, ...) this store never
        # actually produces, so the cast - not the bare call - is what the
        # rest of the module reads as the true type.
        return cast(
            "frozenset[str]", self._cache.get(_KEYS_OF_TAG + tag, default=frozenset())
        )

    def _tags_of(self, key: str) -> frozenset[str]:
        """Every tag currently recorded as carried by ``key``."""
        return cast(
            "frozenset[str]",
            self._cache.get(_TAGS_OF_KEY + key, default=frozenset()),
        )
