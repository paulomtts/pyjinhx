import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar

logger = logging.getLogger("pyjinhx")

if TYPE_CHECKING:
    from .base import BaseComponent


_registry_context: ContextVar[dict[str, "BaseComponent"]] = ContextVar(
    "component_registry", default={}
)


class Registry:
    """
    Central registry for component classes and instances.

    Provides two registries:
    - Class registry: Maps component class names to their types (process-wide).
    - Instance registry: Maps component IDs to instances (context-local, thread-safe).

    Component classes are auto-registered when subclassing BaseComponent. Instances are
    registered upon instantiation, enabling cross-referencing in templates by ID.
    """

    _class_registry: ClassVar[dict[str, type["BaseComponent"]]] = {}

    @classmethod
    def register_class(cls, component_class: type["BaseComponent"]) -> None:
        """
        Register a component class by its name.

        Called automatically when subclassing BaseComponent.

        Args:
            component_class: The component class to register.
        """
        class_name = component_class.__name__
        if class_name in cls._class_registry:
            logger.warning(
                f"Component class {class_name} is already registered. Overwriting..."
            )
        cls._class_registry[class_name] = component_class

    @classmethod
    def get_classes(cls) -> dict[str, type["BaseComponent"]]:
        """
        Return a copy of all registered component classes.

        Returns:
            Dictionary mapping class names to component class types.
        """
        return cls._class_registry.copy()

    @classmethod
    def clear_classes(cls) -> None:
        """Remove all registered component classes. Useful for testing."""
        cls._class_registry.clear()

    @classmethod
    def register_instance(cls, component: "BaseComponent") -> None:
        """
        Register a component instance by its ID.

        Called automatically on instantiation.

        Args:
            component: The component instance to register.
        """
        registry = _registry_context.get()
        if component.id in registry:
            logger.warning(
                f"While registering{component.__class__.__name__}(id={component.id}) found an existing component with the same id. Overwriting..."
            )
        registry[component.id] = component

    @classmethod
    def get_instances(cls) -> dict[str, "BaseComponent"]:
        """
        Return all registered component instances in the current context.

        Returns:
            Dictionary mapping component IDs to component instances.
        """
        return _registry_context.get()

    @classmethod
    def clear_instances(cls) -> None:
        """Remove all registered component instances from the current context."""
        _registry_context.set({})
