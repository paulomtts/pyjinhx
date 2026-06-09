from __future__ import annotations

import typing
from typing import Annotated, Any, get_args, get_origin

from pydantic.fields import FieldInfo

from .keys import coerce_load_key_str


class PjxLoad:
    """Marker for ``Annotated[..., PjxLoad()]`` fields stamped as ``data-pjx-load``."""


def _metadata_has_pjx_load(metadata: tuple[Any, ...]) -> bool:
    return any(isinstance(meta, PjxLoad) for meta in metadata)


def _annotation_has_pjx_load(annotation: Any) -> bool:
    if get_origin(annotation) is Annotated:
        return _metadata_has_pjx_load(get_args(annotation)[1:])
    return False


def _field_has_pjx_load(field_info: FieldInfo) -> bool:
    if _metadata_has_pjx_load(field_info.metadata):
        return True
    return _annotation_has_pjx_load(field_info.annotation)


def pjx_load_field_names(model_cls: type[Any]) -> list[str]:
    names: list[str] = []
    for name, field_info in model_cls.model_fields.items():
        if _field_has_pjx_load(field_info):
            names.append(name)
    if names:
        return names
    for name, annotation in getattr(model_cls, "__annotations__", {}).items():
        if _annotation_has_pjx_load(annotation):
            names.append(name)
    return names


def resolve_pjx_load_field(model_cls: type[Any]) -> str | None:
    names = pjx_load_field_names(model_cls)
    if not names:
        return None
    if len(names) > 1:
        raise TypeError(
            f"{model_cls.__name__} declares multiple PjxLoad fields {names!r}; "
            f"at most one is allowed."
        )
    return names[0]


def validate_pjx_load_subclass(
    cls: type[Any],
    *,
    keyed: bool,
) -> None:
    names = pjx_load_field_names(cls)
    if keyed and len(names) != 1:
        raise TypeError(
            f"{cls.__name__}.load() takes a resource argument; declare exactly "
            f"one field as Annotated[..., PjxLoad()]."
        )
    if not keyed and names:
        raise TypeError(
            f"{cls.__name__}.load() takes no resource argument; PjxLoad fields "
            f"are not allowed ({names!r})."
        )


def pjx_load_value(instance: Any) -> str | None:
    field_name = getattr(type(instance), "_pjx_load_field", None)
    if field_name is None:
        return None
    return coerce_load_key_str(getattr(instance, field_name, None))
