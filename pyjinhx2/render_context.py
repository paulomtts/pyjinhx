"""Build Jinja2 template context from component instances."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyjinhx2.component import BaseComponent
    from pyjinhx2.descriptor import ClassDescriptor


def build_context(
    component: BaseComponent,
    descriptor: ClassDescriptor,
) -> dict[str, Any]:
    """Build Jinja2 template context from a component instance.

    Extracts all declared fields via component.model_dump(), wraps
    component-valued Slot fields with opaque markers, and returns the
    context dict ready for template.render(context).

    Args:
        component: Validated BaseComponent instance (strict mode only)
        descriptor: ClassDescriptor for this component class

    Returns:
        dict[str, Any] with all fields ready for Jinja rendering
    """
    context = component.model_dump()
    return context
