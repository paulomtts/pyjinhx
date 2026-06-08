from enum import StrEnum

from ..utils import ReactiveKey, coerce_load_key, coerce_reactive_keys


class StateKey(StrEnum):
    """
    Base class for app-level reactive state keys.

    Subclass and declare members; use the enum in ``reacts_to``, ``dirtied``,
    and ``@mutates`` — all normalize to their string values.
    """


def instance_key(stem: str, key: str | int) -> str:
    """Build an instance-tier dirty key, e.g. ``instance_key("todo", 42)`` → ``"todo:42"``."""
    return f"{stem}:{coerce_load_key(key)}"


def dirty_keys(
    instance_stem: str,
    key: str | int,
    *collection: ReactiveKey,
) -> set[str]:
    """
    Build a two-tier dirty set for instance-keyed mutations.

    Returns the expanded instance key plus any collection-tier keys, e.g.
    ``dirty_keys("todo", 42, "todos")`` → ``{"todo:42", "todos"}``.
    """
    return {instance_key(instance_stem, key), *coerce_reactive_keys(collection)}
