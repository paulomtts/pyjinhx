"""Per-backend failure state: what a raising tier-2 backend is allowed to cost.

A cache is an optimization, so a backend that raises must not take a request
down with it. What the failure costs differs by operation: a dropped get() or
put() costs speed, while a dropped eviction risks serving stale data, so an
evict failure marks the backend degraded and its reads stop being trusted until
a write lands again.

State is keyed on ``id(backend)`` because a backend is anything satisfying a
structural protocol - it need not be hashable, so keying a dict on the backend
itself is not available. Each entry carries a weak reference so a recycled id
cannot hand a fresh backend a dead one's flags.
"""

from __future__ import annotations

import logging
import weakref
from dataclasses import dataclass

logger = logging.getLogger("pyjinhx")


@dataclass
class _Health:
    """One backend instance's failure state for the life of this process."""

    ref: weakref.ref[object] | None = None
    logged: bool = False
    degraded: bool = False


_health: dict[int, _Health] = {}


def is_degraded(backend: object) -> bool:
    """Whether this backend's reads are currently not to be trusted."""
    state = _health.get(id(backend))
    return state is not None and _is_same(state, backend) and state.degraded


def note_failure(
    backend: object, operation: str, exc: BaseException, *, degrade: bool
) -> None:
    """Record a backend call that raised, warning at most once per backend.

    Args:
        backend: The backend instance whose call raised.
        operation: The method that raised, named for the log line.
        exc: What it raised, summarized in the log line.
        degrade: Whether this failure means the backend's entries can no longer
            be trusted - true for a failed eviction, false for a read or write.
    """
    state = _state(backend)
    if degrade:
        state.degraded = True
    # One warning per backend, not one per failing call: a backend that is down
    # fails on every request, and a log line per request buries the first one.
    if state.logged:
        return
    state.logged = True
    logger.warning(
        "pyjinhx cache backend %s failed on %s (%s: %s); the cache is being "
        "bypassed. Further failures from this backend are not logged.",
        type(backend).__name__,
        operation,
        type(exc).__name__,
        exc,
    )


def note_write_success(backend: object) -> None:
    """Record a write that landed, clearing any degraded flag."""
    # Deliberately does not create an entry: a backend that has never failed
    # needs no state, and this runs on every successful tier-2 write.
    state = _health.get(id(backend))
    if state is not None and _is_same(state, backend):
        state.degraded = False


def reset_backend_health() -> None:
    """Drop every backend's recorded failure state.

    Exists for tests, which need one test's failing backend to leave nothing
    behind for the next.
    """
    _health.clear()


def _state(backend: object) -> _Health:
    """This backend's state, fresh if the id was never used or was recycled."""
    existing = _health.get(id(backend))
    if existing is not None and _is_same(existing, backend):
        return existing
    fresh = _Health(ref=_weak_ref(backend))
    _health[id(backend)] = fresh
    return fresh


def _is_same(state: _Health, backend: object) -> bool:
    """Whether this state was recorded for this very backend object."""
    # No reference means the object could not be weakly referenced, so the id
    # is all there is to go on - the same position this module would be in
    # without weakrefs at all, rather than a new risk.
    if state.ref is None:
        return True
    return state.ref() is backend


def _weak_ref(backend: object) -> weakref.ref[object] | None:
    """A weak reference to this backend, or None if it does not support one."""
    try:
        return weakref.ref(backend)
    except TypeError:
        return None
