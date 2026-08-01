"""The request-scoped load cache: ``(class, key) -> load() result``.

Keys are plain ``(cls, key)`` tuples - both halves are already hashable, so
there is no string composite to build or parse back. Entries live in the dict
``session.get_cache_store()`` hands out, which ``request_scope()`` replaces per
request; this module owns no state of its own.

``cache_get()`` answers ``None`` for a miss, which a legitimately cached ``None``
would be indistinguishable from - ``cache_has()`` is the way to tell the two
apart, and the reason a private sentinel does the lookup internally rather than
a plain ``.get()``.

``cache_put()`` is the only mutator. Outside a request scope every function is a
no-op: ``get_cache_store()`` answers a throwaway ``{}``, so writes vanish and
reads miss. A cache that does nothing is a correct cache, so nothing raises.
"""

from pyjinhx2.session import get_cache_store

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


def cache_put(cls: type, key: object, value: object) -> None:
    """Cache a load result for this class and key, replacing any existing entry.

    The only function that mutates the cache store.

    Args:
        cls: The component class the value was loaded for.
        key: That instance's load key; any hashable value.
        value: The load result to store, kept as-is.
    """
    get_cache_store()[make_key(cls, key)] = value
