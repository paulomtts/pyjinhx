from __future__ import annotations

import functools
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, TypeVar

from .cache import invalidate
from ..utils import ReactiveKey, coerce_reactive_keys

_mutation_dirtied: ContextVar[set[str] | None] = ContextVar(
    "mutation_dirtied", default=None
)
_reactive_render_consumed: ContextVar[bool] = ContextVar(
    "reactive_render_consumed", default=False
)

F = TypeVar("F", bound=Callable[..., Any])


def pending_dirtied() -> set[str]:
    """Return accumulated dirtied keys for the current request scope."""
    registry = _mutation_dirtied.get()
    if registry is None:
        return set()
    return set(registry)


def clear_mutations() -> None:
    """Reset accumulated dirtied keys and render-consumed flag."""
    _mutation_dirtied.set(set())
    _reactive_render_consumed.set(False)


def _accumulate_dirtied(keys: Iterable[ReactiveKey]) -> None:
    normalized = coerce_reactive_keys(keys)
    if not normalized:
        return
    current = _mutation_dirtied.get()
    if current is None:
        current = set()
        _mutation_dirtied.set(current)
    current.update(normalized)


def mark_reactive_render_consumed() -> None:
    """Record that a reactive render consumed pending mutations."""
    _reactive_render_consumed.set(True)
    _mutation_dirtied.set(set())


def reactive_render_was_consumed() -> bool:
    return _reactive_render_consumed.get()


def resolve_effective_dirtied(
    *,
    dirtied: set[ReactiveKey] | None,
    mounted: object | None,
    own_keys: set[str],
) -> set[str]:
    """
    Resolve dirtied keys for a reactive render.

    When ``dirtied`` is omitted and reactive mode is active (``mounted`` set),
    merge the primary's own keys with pending mutations from ``@mutates``.
    Explicit ``dirtied`` (including an empty set) always wins.
    """
    if dirtied is not None:
        return coerce_reactive_keys(dirtied)
    if mounted is None:
        return own_keys
    return own_keys | pending_dirtied()


def mutates(*keys: ReactiveKey) -> Callable[[F], F]:
    """
    Decorator for store mutation methods.

    Invalidates the load() cache for ``keys`` and accumulates them as pending
    dirtied for the next reactive ``render()`` when ``dirtied`` is omitted.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            normalized = coerce_reactive_keys(keys)
            if normalized:
                invalidate(normalized)
                _accumulate_dirtied(normalized)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


@contextmanager
def mutation_scope(*keys: ReactiveKey) -> Generator[None, None, None]:
    """
    Context manager that accumulates dirtied keys for a block.

    Keys passed to the scope are added on entry (and invalidate the cache).
    """
    normalized = coerce_reactive_keys(keys)
    try:
        yield
    finally:
        if normalized:
            invalidate(normalized)
            _accumulate_dirtied(normalized)
