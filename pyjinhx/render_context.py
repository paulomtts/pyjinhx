"""Build Jinja2 template context from component instances."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from markupsafe import Markup

from pyjinhx.component import BaseComponent
from pyjinhx.markers import ComponentNode


def _wrap_slot_value(
    value: object,
    owner_name: str,
    owner_template: Path | None,
    field_name: str,
) -> object:
    """Wrap the components inside a slot value, one opaque node each.

    A list or dict slot comes back as a plain list or dict so a template can
    walk it with ``{% for %}``: opacity is a per-child guarantee (ADR 0003),
    and a ComponentNode refuses to be iterated, so wrapping the container
    itself would make the collection unusable. A plain string comes back as
    ``Markup`` — a slot's string value is authored markup. Anything else — an
    empty container, a non-component item — passes through untouched.
    """

    def node(component: BaseComponent) -> ComponentNode:
        return ComponentNode(
            component,
            owner_name=owner_name,
            owner_template=owner_template,
            field_name=field_name,
        )

    if isinstance(value, str):
        # A string on a slot field is authored markup, not user data: ADR 0003
        # exempts it from autoescape. Only slot fields reach this function, so
        # ordinary str fields keep escaping.
        return Markup(value)
    if isinstance(value, BaseComponent):
        return node(value)
    if isinstance(value, list):
        return [
            node(item) if isinstance(item, BaseComponent) else item for item in value
        ]
    if isinstance(value, dict):
        return {
            key: node(item) if isinstance(item, BaseComponent) else item
            for key, item in value.items()
        }
    return value


def build_context(
    component: BaseComponent,
    descriptor: Any,
) -> dict[str, Any]:
    """Build Jinja2 template context from a component instance.

    Extracts all declared fields via component.model_dump(), wraps
    component-valued Slot fields with opaque markers, and returns the
    context dict ready for template.render(context).

    Args:
        component: Validated BaseComponent instance (strict mode only)
        descriptor: ClassDescriptor for this component (has slot_fields attr)

    Returns:
        dict[str, Any] with all fields ready for Jinja rendering
    """
    context = component.model_dump()

    # Wrap component-valued Slot fields with ComponentNode
    for slot_field_name in descriptor.slot_fields:
        if slot_field_name in context:
            # Get the actual component value from the component instance
            # (not from the serialized dict)
            actual_value = getattr(component, slot_field_name)
            context[slot_field_name] = _wrap_slot_value(
                actual_value,
                owner_name=type(component).__name__,
                owner_template=getattr(descriptor, "template_path", None),
                field_name=slot_field_name,
            )

    return context
