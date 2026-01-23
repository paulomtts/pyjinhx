import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar

logger = logging.getLogger("pyjinhx")

if TYPE_CHECKING:
    from .base import BaseComponent


_registry_context: ContextVar[dict[str, "BaseComponent"] | None] = ContextVar(
    "component_registry", default=None
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
    def make_key(cls, class_name: str, instance_id: str) -> str:
        """Generate a registry key from component class name and instance ID."""
        return f"{class_name}_{instance_id}"

    @classmethod
    def register_instance(cls, component: "BaseComponent") -> None:
        """
        Register a component instance by its ID.

        Called automatically on instantiation.

        Args:
            component: The component instance to register.
        """
        registry = cls.get_instances()
        key = cls.make_key(type(component).__name__, component.id)
        if key in registry:
            logger.warning(
                f"While registering {type(component).__name__}(id={component.id}) "
                f"found an existing component with key '{key}'. Overwriting..."
            )
        registry[key] = component

    @classmethod
    def get_instances(cls) -> dict[str, "BaseComponent"]:
        """
        Return all registered component instances in the current context.

        Returns:
            Dictionary mapping component IDs to component instances.
        """
        registry = _registry_context.get()
        if registry is None:
            registry = {}
            _registry_context.set(registry)
        return registry

    @classmethod
    def clear_instances(cls) -> None:
        """Remove all registered component instances from the current context."""
        _registry_context.set({})

    @classmethod
    @contextmanager
    def request_scope(cls):
        """
        Context manager for request-scoped component instances.

        Creates a fresh instance registry on entry and restores
        the previous state on exit.

        Usage:
            with Registry.request_scope():
                # components registered here won't persist
        """
        token = _registry_context.set({})
        try:
            yield
        finally:
            _registry_context.reset(token)
