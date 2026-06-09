from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .registry import Registry
from ..utils import stamp_root_attributes

if TYPE_CHECKING:
    from .base import BaseComponent


def build_render_context(context: dict[str, Any]) -> dict[str, Any]:
    render_context = dict(context)
    for instance in Registry.get_instances().values():
        render_context.setdefault(instance.id, instance)
    return render_context


def stamp_reactive_markup(markup: str, component: BaseComponent) -> str:
    if not getattr(type(component), "_pjx_reactive", False):
        return markup

    from pyjinhx.reactive.pjx_load import pjx_load_value

    attrs = {
        "data-pjx-id": component.id,
        "data-pjx-type": type(component).__name__,
        "data-pjx-hash": component.state_hash(),
    }
    load_value = pjx_load_value(component)
    if load_value is not None:
        attrs["data-pjx-load"] = load_value
    return stamp_root_attributes(markup, attrs)
