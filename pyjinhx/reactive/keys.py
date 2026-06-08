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


def interpolate_reactive_keys(
    keys: Iterable[str],
    key: str | None,
    *,
    keyed: bool = False,
) -> set[str]:
    """
    Expand declared reactive keys for a component instance.

    For singletons (``key is None``), declared keys are returned as-is.

    For instance-keyed components, bare stems (e.g. ``"todo"``) expand to
    ``"todo:<key>"``. When a plural sibling is present (e.g. ``"user"`` with
    ``"users"``), the singular is the instance stem and the plural stays global.
    Legacy ``"{key}"`` placeholders are still expanded for backward compatibility.
    """
    if key is None:
        return set(keys)

    declared = set(keys)
    if not keyed:
        return declared

    result: set[str] = set()
    for declared_key in declared:
        if "{key}" in declared_key:
            result.add(declared_key.replace("{key}", key))
        elif ":" in declared_key:
            result.add(declared_key)
        elif f"{declared_key}s" in declared:
            result.add(f"{declared_key}:{key}")
        elif any(
            declared_key == f"{other}s" for other in declared if other != declared_key
        ):
            result.add(declared_key)
        else:
            result.add(f"{declared_key}:{key}")
    return result


class StateKey(StrEnum):
    """
    Base class for app-level reactive state keys.

    Subclass and declare members; use the enum in ``reacts_to``, ``dirtied``,
    and ``@mutates`` — all normalize to their string values.
    """

    @staticmethod
    def instance_key(stem: str, key: str | int) -> str:
        """Build an instance-tier dirty key, e.g. ``StateKey.instance_key("todo", 42)`` → ``"todo:42"``."""
        return f"{stem}:{coerce_reactive_key(key)}"

    @staticmethod
    def dirty_keys(
        instance_stem: str,
        key: str | int,
        *collection: ReactiveKey,
    ) -> set[str]:
        """
        Build a two-tier dirty set for instance-keyed mutations.

        Returns the expanded instance key plus any collection-tier keys, e.g.
        ``StateKey.dirty_keys("todo", 42, "todos")`` → ``{"todo:42", "todos"}``.
        """
        return {
            StateKey.instance_key(instance_stem, key),
            *coerce_reactive_keys(collection),
        }
