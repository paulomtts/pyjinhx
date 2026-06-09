from enum import Enum, StrEnum
from collections.abc import Iterable

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


def coerce_load_key_str(key: object) -> str | None:
    """Like ``coerce_reactive_key``, but returns ``None`` for a ``None`` input."""
    if key is None:
        return None
    return coerce_reactive_key(key)


class StateKey(StrEnum):
    """
    Base class for app-level reactive state keys.

    Subclass and declare members; use the enum in ``reacts_to`` and ``@mutates`` —
    all normalize to their string values.
    """
