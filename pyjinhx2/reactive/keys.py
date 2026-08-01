"""The reactive key vocabulary: the strings that name mutable app state.

Stateless by construction — type definitions and pure functions only. Everything
request-scoped (the dirtied-key set, ``@mutates``, ``dirty()``) lives in
``pyjinhx2.reactive.mutations`` and imports from here.
"""

from collections.abc import Iterable
from enum import Enum, StrEnum

ReactiveKey = str | Enum


def coerce_reactive_key(key: object) -> str:
    """Normalize a reactive key: unwrap enums to ``.value``, then ``str``."""
    if isinstance(key, Enum):
        key = key.value
    return str(key)


def coerce_load_key_str(value: object) -> str | None:
    """Normalize a component's load key to a string; ``None`` stays ``None``.

    A component with no PjxKey field has no load key at all, and that absence
    is itself the cache key every instance of the class shares - so ``None``
    passes through rather than becoming the string ``"None"``.
    """
    if value is None:
        return None
    return coerce_reactive_key(value)


def coerce_reactive_keys(keys: Iterable[object] | None) -> set[str]:
    """Normalize a collection of reactive dependency keys."""
    if not keys:
        return set()
    return {coerce_reactive_key(key) for key in keys}


class MutationKey(StrEnum):
    """
    Base class for app-level reactive state keys.

    Subclass and declare members; use the members in ``react={...}`` and ``@mutates`` —
    all normalize to their string values.
    """


class DynamicReactiveKey(str):
    """A key produced by ``reactive_key()`` — accepted by ``dirty()``/``@mutates()``
    alongside ``MutationKey`` members. Not constructed directly."""


def reactive_key(key: MutationKey, arg: object) -> DynamicReactiveKey:
    """
    Build a per-instance reactive key from a static ``MutationKey`` and an
    instance's own load-key, e.g. ``reactive_key(ChatKeys.MESSAGE, message_id)``.

    Use the result with ``dirty()``/``@mutates()`` to invalidate/reload only the
    one mounted instance whose load-key matches ``arg``, instead of every
    instance reacting to ``key``.
    """
    return DynamicReactiveKey(f"{coerce_reactive_key(key)}:{arg}")
