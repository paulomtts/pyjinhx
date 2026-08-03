"""``@mutates`` and ``dirty()``: the two ways an app marks reactive keys dirty."""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from pyjinhx.reactive.keys import (
    DynamicReactiveKey,
    MutationKey,
    coerce_reactive_keys,
    reactive_key,
)
from pyjinhx.session import add_dirtied

F = TypeVar("F", bound=Callable[..., Any])


def _require_mutation_keys(keys: tuple[Any, ...], caller: str) -> None:
    invalid = sorted(
        repr(key)
        for key in keys
        if not isinstance(key, (MutationKey, DynamicReactiveKey))
    )
    if invalid:
        raise TypeError(
            f"{caller} only accepts MutationKey members or reactive_key() values; "
            f"got {', '.join(invalid)}"
        )


def mutates(
    *keys: MutationKey, key: Callable[..., object] | None = None
) -> Callable[[F], F]:
    """
    Decorator for mutation methods.

    Records ``keys`` in this request's dirtied set after the wrapped function
    returns. Keys must be ``MutationKey`` members or ``reactive_key()`` values.

    Pass ``key=`` to derive a per-instance key instead of dirtying ``keys``
    directly - it's called with the wrapped function's own arguments and its
    return value feeds ``reactive_key()`` for every key in ``keys``, e.g.
    ``@mutates(Keys.TODO, key=lambda self, todo_id: todo_id)``.
    """
    # Eager validation: a bad key fails when the class body is executed, not on
    # the first call at runtime.
    _require_mutation_keys(keys, "@mutates")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            active_keys: tuple[object, ...] = keys
            if key is not None:
                arg = key(*args, **kwargs)
                active_keys = tuple(reactive_key(k, arg) for k in keys)
            add_dirtied(coerce_reactive_keys(active_keys))
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def dirty(*keys: MutationKey | DynamicReactiveKey) -> None:
    """
    Imperatively dirty reactive keys, like ``@mutates`` without a decorator.

    Records ``keys`` in this request's dirtied set. Keys must be ``MutationKey``
    members or ``reactive_key()`` values.
    """
    _require_mutation_keys(keys, "dirty()")
    add_dirtied(coerce_reactive_keys(keys))
