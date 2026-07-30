"""Build Jinja2 template context from component instances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyjinhx2.component import BaseComponent

from pyjinhx2.markers import ComponentNode


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
            # Only wrap BaseComponent instances; strings pass through
            from pyjinhx2.component import BaseComponent

            if isinstance(actual_value, BaseComponent):
                context[slot_field_name] = ComponentNode(actual_value)

    return context
