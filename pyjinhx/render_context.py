"""Build Jinja2 template context from component instances."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from markupsafe import Markup

from pyjinhx._component import BaseComponent
from pyjinhx.markers import ComponentNode, finalize_slot_node


def _slot_item_html(item: object) -> str:
    """The markup one collection entry contributes when the container itself
    is interpolated bare (``{{ content }}``, no ``{% for %}``).

    A ComponentNode is swapped for its placeholder token exactly the way a
    lone component-valued slot already is, so the same post-render
    substitution pass fills in its real markup. Anything else is escaped
    like ordinary template data — a collection entry is not itself
    author-declared markup the way the slot's own string form is.
    """
    if isinstance(item, ComponentNode):
        return str(finalize_slot_node(item))
    return str(Markup.escape(item))


class _SlotList(list):
    """A list of slot entries that also renders composed markup when
    interpolated directly, so ``{{ content }}`` and ``{% for %}`` both work.
    """

    def __html__(self) -> str:
        return "".join(_slot_item_html(item) for item in self)


class _SlotDict(dict):
    """A dict of slot entries that also renders composed markup when
    interpolated directly, so ``{{ content }}`` and ``{% for %}`` both work.
    """

    def __html__(self) -> str:
        return "".join(_slot_item_html(item) for item in self.values())


def _wrap_slot_value(
    value: object,
    owner_name: str,
    owner_template: Path | None,
    field_name: str,
) -> object:
    """Wrap the components inside a slot value, one opaque node each.

    A list or dict slot comes back as a list/dict subclass so a template can
    still walk it with ``{% for %}`` (opacity is a per-child guarantee, ADR
    0003, and a ComponentNode refuses to be iterated, so wrapping the
    container itself would make the collection unusable) while also
    composing correctly when interpolated bare (``{{ content }}``, no loop).
    A plain string comes back as ``Markup`` — a slot's string value is
    authored markup. Anything else — an empty container, a non-component
    item — passes through untouched.
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
        return _SlotList(
            node(item) if isinstance(item, BaseComponent) else item for item in value
        )
    if isinstance(value, dict):
        return _SlotDict(
            (key, node(item) if isinstance(item, BaseComponent) else item)
            for key, item in value.items()
        )
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
