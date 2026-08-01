"""The request-scoped load cache: ``(class, key) -> load() result``.

Keys are plain ``(cls, key)`` tuples - both halves are already hashable, so
there is no string composite to build or parse back. Entries live in the dict
``session.get_cache_store()`` hands out, which ``request_scope()`` replaces per
request; this module owns no state of its own.

``cache_get()`` answers ``None`` for a miss, which a legitimately cached ``None``
would be indistinguishable from - ``cache_has()`` is the way to tell the two
apart, and the reason a private sentinel does the lookup internally rather than
a plain ``.get()``.

``cache_put()`` is the only mutator, and the only writer of the reverse index -
the ``reactive key -> {(cls, key)}`` map ``session.get_cache_reverse()`` hands
out, which ``invalidate()`` reads to evict exactly the entries a dirtied key
touched. Outside a request scope every function is a no-op: ``get_cache_store()``
and ``get_cache_reverse()`` answer throwaway containers, so writes vanish and
reads miss. A cache that does nothing is a correct cache, so nothing raises.
"""

from collections.abc import Iterable

from pyjinhx2.session import get_cache_reverse, get_cache_store

# Distinguishes "no entry" from an entry whose value happens to be None.
_MISS = object()


def make_key(cls: type, key: object) -> tuple[type, object]:
    """Build the composite cache key for a component class and a load key.

    Args:
        cls: The component class the cached value was loaded for.
        key: That instance's load key; any hashable value.

    Returns:
        The ``(cls, key)`` pair used as the cache store's dict key.
    """
    return (cls, key)


def cache_get(cls: type, key: object) -> object | None:
    """Return the value cached for this class and key, or None.

    A miss is ordinary, not exceptional, so this returns None rather than
    raising. Use ``cache_has()`` when None could also be a cached value.

    Args:
        cls: The component class.
        key: That instance's load key.

    Returns:
        The cached value, or None when nothing is cached - including every
        lookup made outside an active request scope.
    """
    value = get_cache_store().get(make_key(cls, key), _MISS)
    if value is _MISS:
        return None
    return value


def cache_has(cls: type, key: object) -> bool:
    """Report whether this class and key have a cached entry.

    Args:
        cls: The component class.
        key: That instance's load key.

    Returns:
        True when an entry exists, whatever its value. Always False outside an
        active request scope.
    """
    return make_key(cls, key) in get_cache_store()


def cache_put(
    cls: type, key: object, value: object, react_keys: Iterable[str] = ()
) -> None:
    """Cache a load result for this class and key, replacing any existing entry.

    The only function that mutates the cache store.

    Args:
        cls: The component class the value was loaded for.
        key: That instance's load key; any hashable value.
        value: The load result to store, kept as-is.
        react_keys: Normalized reactive keys this result depends on. Dirtying
            any of them evicts this entry. Defaults to none, which makes the
            entry plain memoization that only a fresh request clears.
    """
    cache_key = make_key(cls, key)
    reverse = get_cache_reverse()
    # A re-put may depend on a different set of keys than the entry it replaces,
    # so drop every old membership before re-indexing rather than adding to it.
    _unindex(reverse, cache_key)
    for react_key in react_keys:
        reverse.setdefault(react_key, set()).add(cache_key)
    get_cache_store()[cache_key] = value


def invalidate(dirtied_keys: Iterable[str]) -> None:
    """Evict every cache entry that depends on any of these reactive keys.

    Outside a request scope there is nothing indexed and nothing to drop, so
    this is a silent no-op like the rest of the module.

    Args:
        dirtied_keys: Normalized string keys, as produced by
            coerce_reactive_keys() and collected by session.add_dirtied().
    """
    reverse = get_cache_reverse()
    store = get_cache_store()
    evicted: set[tuple[type, object]] = set()
    for react_key in dirtied_keys:
        evicted |= reverse.get(react_key, set())
    for cache_key in evicted:
        # An entry reachable from two dirtied keys is popped once; the second
        # pop is an ordinary miss, not an error.
        store.pop(cache_key, None)
        # Clean every key the entry was registered under, not just the dirtied
        # ones that matched: the entry is gone from the store, so any surviving
        # membership would name a cache_key nothing can look up.
        _unindex(reverse, cache_key)


def _unindex(
    reverse: dict[str, set[tuple[type, object]]], cache_key: tuple[type, object]
) -> None:
    """Remove a cache key from every reverse-index set that holds it."""
    for entries in reverse.values():
        entries.discard(cache_key)
