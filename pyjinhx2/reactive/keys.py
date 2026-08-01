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


def coerce_reactive_keys(keys: Iterable[object] | None) -> set[str]:
    """Normalize a collection of reactive dependency keys."""
    if not keys:
        return set()
    return {coerce_reactive_key(key) for key in keys}
