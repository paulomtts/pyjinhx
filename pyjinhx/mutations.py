from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from contextvars import ContextVar
from typing import Any, ClassVar, TypeVar

from .keys import MutationKey, ReactiveKey, coerce_reactive_keys
from .cache import LoadCache

F = TypeVar("F", bound=Callable[..., Any])


class MutationTracker:
    """Request-scoped accumulation of dirtied reactive keys from mutations."""

    _dirtied: ClassVar[ContextVar[set[str] | None]] = ContextVar(
        "mutation_dirtied", default=None
    )
    _render_consumed: ClassVar[ContextVar[bool]] = ContextVar(
        "reactive_render_consumed", default=False
    )

    @classmethod
    def pending(cls) -> set[str]:
        registry = cls._dirtied.get()
        if registry is None:
            return set()
        return set(registry)

    @classmethod
    def clear(cls) -> None:
        cls._dirtied.set(set())
        cls._render_consumed.set(False)

    @classmethod
    def record(cls, keys: Iterable[ReactiveKey]) -> None:
        normalized = coerce_reactive_keys(keys)
        if not normalized:
            return
        LoadCache.invalidate(normalized)
        current = cls._dirtied.get()
        if current is None:
            current = set()
            cls._dirtied.set(current)
        current.update(normalized)

    @classmethod
    def mark_render_consumed(cls) -> None:
        cls._render_consumed.set(True)
        cls._dirtied.set(set())

    @classmethod
    def render_was_consumed(cls) -> bool:
        return cls._render_consumed.get()


def mutates(*keys: MutationKey) -> Callable[[F], F]:
    """
    Decorator for store mutation methods.

    Invalidates the load cache for ``keys`` and accumulates them as pending
    dirtied for the next reactive ``render()``. Keys must be ``MutationKey``
    members.
    """
    invalid = sorted(repr(key) for key in keys if not isinstance(key, MutationKey))
    if invalid:
        raise TypeError(f"@mutates only accepts MutationKey members; got {', '.join(invalid)}")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            MutationTracker.record(keys)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
