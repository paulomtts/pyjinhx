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
    Registry for all components.
    """

    _class_registry: ClassVar[dict[str, type["BaseComponent"]]] = {}

    @classmethod
    def register_class(cls, component_class: type["BaseComponent"]) -> None:
        class_name = component_class.__name__
        if class_name in cls._class_registry:
            logger.warning(
                f"Component class {class_name} is already registered. Overwriting..."
            )
        cls._class_registry[class_name] = component_class

    @classmethod
    def get_classes(cls) -> dict[str, type["BaseComponent"]]:
        return cls._class_registry.copy()

    @classmethod
    def clear_classes(cls) -> None:
        cls._class_registry.clear()

    @classmethod
    def register_instance(cls, component: "BaseComponent") -> None:
        registry = _registry_context.get()
        if component.id in registry:
            logger.warning(
                f"While registering{component.__class__.__name__}(id={component.id}) found an existing component with the same id. Overwriting..."
            )
        registry[component.id] = component

    @classmethod
    def get_instances(cls) -> dict[str, "BaseComponent"]:
        return _registry_context.get()

    @classmethod
    def clear_instances(cls) -> None:
        _registry_context.set({})
