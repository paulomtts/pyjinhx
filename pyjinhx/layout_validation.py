from __future__ import annotations

from typing import TYPE_CHECKING

from .registry import Registry

if TYPE_CHECKING:
    from .base import BaseComponent


class LayoutConfigurationError(Exception):
    """Raised when base_layout configuration violates pyjinhx layout rules."""


_layout_validation_enabled: bool = False


def enable_layout_validation() -> None:
    """Enable render-time checks that root full-page renders use a layout component."""
    global _layout_validation_enabled
    _layout_validation_enabled = True


def disable_layout_validation() -> None:
    """Disable render-time layout validation."""
    global _layout_validation_enabled
    _layout_validation_enabled = False


def layout_validation_enabled() -> bool:
    return _layout_validation_enabled


def validate_layout_registry() -> None:
    """
    Require exactly one registered component class with explicit ``base_layout=True``.

    Call after all component modules are imported (e.g. FastAPI startup). Apps that
    use raw Jinja shells with ``client_script()`` and no declared layout should skip this.
    """
    declared = [
        name
        for name, component_class in Registry.get_classes().items()
        if getattr(component_class, "_pjx_layout_declared", False)
    ]
    if len(declared) == 1:
        return
    if not declared:
        raise LayoutConfigurationError(
            "Expected exactly one component class with base_layout=True in the "
            "registry, found 0. Mark your page shell with base_layout=True, or use "
            "client_script() in a raw Jinja layout and skip validate_layout_registry()."
        )
    raise LayoutConfigurationError(
        "Expected exactly one component class with base_layout=True in the registry, "
        f"found {len(declared)}: {', '.join(sorted(declared))}"
    )


def validate_root_is_layout(component: BaseComponent) -> None:
    """Require the root component of a full-page render to be a layout type."""
    component_type = type(component).__name__
    if getattr(type(component), "_pjx_layout", False):
        return
    raise LayoutConfigurationError(
        f"Root render must use a base_layout component; got {component_type}"
    )
