"""The request-scoped load cache: ``(class, key) -> load() result``.

Keys are plain ``(cls, key)`` tuples - both halves are already hashable, so
there is no string composite to build or parse back. Entries live in the dict
``session.get_cache_store()`` hands out, which ``request_scope()`` replaces per
request; this module owns no state of its own.

``cache_get()`` answers ``None`` for a miss, which a legitimately cached ``None``
would be indistinguishable from - ``cache_has()`` is the way to tell the two
apart, and the reason a private sentinel does the lookup internally rather than
a plain ``.get()``.

``cache_put()`` is the only mutator, and the only writer of the two indexes -
the ``reactive key -> {(cls, key)}`` map ``session.get_cache_reverse()`` hands
out, which ``invalidate()`` reads to evict exactly the entries a dirtied key
touched, and its mirror ``session.get_cache_forward()``, which names the keys a
single entry sits under so un-indexing costs that entry's own key count instead
of a walk over every bucket. Outside a request scope every function is a no-op:
the session getters answer throwaway containers, so writes vanish and reads
miss. A cache that does nothing is a correct cache, so nothing raises.

``invalidate()`` is the one function here that looks past this request:
``wrapped_load`` writes each cross-request entry under the same reactive keys
this module reverse-indexes by, so the dirtied keys pass straight through to
the configured backend's ``evict()`` as tags. Nothing else in this module knows
that tier exists.
"""

from collections.abc import Iterable

from pyjinhx.reactive.backend_health import note_failure
from pyjinhx.session import get_cache_forward, get_cache_reverse, get_cache_store

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
    forward = get_cache_forward()
    # A re-put may depend on a different set of keys than the entry it replaces,
    # so drop every old membership before re-indexing rather than adding to it.
    _unindex(reverse, forward, cache_key)
    for react_key in react_keys:
        reverse.setdefault(react_key, set()).add(cache_key)
        forward.setdefault(cache_key, set()).add(react_key)
    get_cache_store()[cache_key] = value


def invalidate(dirtied_keys: Iterable[str]) -> None:
    """Evict every cache entry that depends on any of these reactive keys.

    Both tiers are swept: this request's store, and the configured cross-request
    backend, where the same keys are the tags its entries were written under.
    Outside a request scope there is nothing indexed in tier 1 and nothing to
    drop there, so that half is a silent no-op like the rest of the module.

    Args:
        dirtied_keys: Normalized string keys, as produced by
            coerce_reactive_keys() and collected by session.add_dirtied().
    """
    # Materialized once because two independent stores read it: a caller that
    # passes a generator would otherwise hand the backend an already-drained
    # iterable and quietly evict from tier 1 only.
    dirtied = tuple(dirtied_keys)
    reverse = get_cache_reverse()
    forward = get_cache_forward()
    store = get_cache_store()
    evicted: set[tuple[type, object]] = set()
    for react_key in dirtied:
        evicted |= reverse.get(react_key, set())
    for cache_key in evicted:
        # An entry reachable from two dirtied keys is popped once; the second
        # pop is an ordinary miss, not an error.
        store.pop(cache_key, None)
        # Clean every key the entry was registered under, not just the dirtied
        # ones that matched: the entry is gone from the store, so any surviving
        # membership would name a cache_key nothing can look up.
        _unindex(reverse, forward, cache_key)
    # Function-local by necessity: config sits above reactive/ and imports the
    # render spine at import time, so a module-scope edge back would be a real
    # cycle. Same escape hatch session.py's request_scope() uses.
    from pyjinhx.config import current_settings

    backend = current_settings().cache_backend
    if backend is not None:
        # The dirtied keys are the tags verbatim - wrapped_load wrote each entry
        # under the very tuple tier 1 reverse-indexes it by - so there is no
        # second index to maintain and nothing to translate here.
        try:
            backend.evict(dirtied)
        # Same rationale as component.py's get()/put() guards: a backend is a
        # plugin, so any failure it raises degrades rather than only the
        # subset this module could predict.
        except Exception as exc:  # noqa: BLE001
            # Unlike a dropped read or write, an eviction that did not happen
            # leaves entries that are now known to be wrong, so the backend
            # stops being read from until a write proves it current again.
            note_failure(backend, "evict", exc, degrade=True)


def _unindex(
    reverse: dict[str, set[tuple[type, object]]],
    forward: dict[tuple[type, object], set[str]],
    cache_key: tuple[type, object],
) -> None:
    """Remove a cache key from every reverse-index set that holds it."""
    # The forward index names exactly the buckets this entry sits in, so the
    # cost is the entry's own key count rather than the whole reverse index.
    for react_key in forward.pop(cache_key, ()):
        reverse[react_key].discard(cache_key)
