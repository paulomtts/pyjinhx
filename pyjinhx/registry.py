import inspect
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar

logger = logging.getLogger("pyjinhx")

if TYPE_CHECKING:
    from .base import BaseComponent
    from .client import ClientBackend


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
    def register_class(
        cls, component_class: type["BaseComponent"], *, replace: bool = False
    ) -> None:
        """
        Register a component class by its name.

        Called automatically when subclassing BaseComponent. Re-registering the
        same name from the same source file (test reruns, hot reload,
        autodiscovery) replaces the previous class. Registering a same-named
        class from a *different* file raises, since `<Name/>` tags would
        silently resolve to whichever class was imported last.

        Args:
            component_class: The component class to register.
            replace: Skip the cross-file collision check and overwrite.
                Set via ``class PJXAvatar(BaseComponent, pjx_replace=True)``.
        """
        class_name = component_class.__name__
        existing = cls._class_registry.get(class_name)
        if existing is not None and existing is not component_class and not replace:
            existing_file = cls._source_file(existing)
            new_file = cls._source_file(component_class)
            if existing_file and new_file and existing_file != new_file:
                raise TypeError(
                    f"Component class {class_name} is already registered by "
                    f"{existing.__module__} ({existing_file}); refusing to overwrite "
                    f"it with {component_class.__module__} ({new_file}). Rename one "
                    f"of the classes, or shadow it intentionally with: "
                    f"class {class_name}(BaseComponent, pjx_replace=True)"
                )
            logger.warning(
                f"Component class {class_name} is already registered. Overwriting..."
            )
        cls._class_registry[class_name] = component_class

    @staticmethod
    def _source_file(component_class: type) -> str | None:
        """Resolve the file a class was defined in, or None (exec'd/REPL code)."""
        try:
            return os.path.realpath(inspect.getfile(component_class))
        except (TypeError, OSError):
            return None

    @classmethod
    def get_classes(cls) -> dict[str, type["BaseComponent"]]:
        """
        Return a copy of all registered component classes.

        Returns:
            Dictionary mapping class names to component class types.
        """
        return cls._class_registry.copy()

    @classmethod
    def get_class(cls, name: str) -> type["BaseComponent"] | None:
        """Return a registered component class by name without copying the registry."""
        return cls._class_registry.get(name)

    @classmethod
    def has_class(cls, name: str) -> bool:
        """Return whether a component class is registered under ``name``."""
        return name in cls._class_registry

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
        registry = _registry_context.get()
        if registry is None:
            logger.warning(
                "Component %s(id=%s) registered outside Registry.request_scope(); "
                "instance will not be available for cross-reference in templates.",
                type(component).__name__,
                component.id,
            )
            return
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
            return {}
        return registry

    @classmethod
    def clear_instances(cls) -> None:
        """Remove all registered component instances from the current context."""
        _registry_context.set({})

    @classmethod
    @contextmanager
    def request_scope(
        cls,
        *,
        load_context: object | None = None,
        client_backend: "ClientBackend | None" = None,
    ) -> Generator[None, None, None]:
        """
        Context manager for request-scoped component instances.

        Creates a fresh instance registry on entry and restores
        the previous state on exit. Also resets mutation tracking,
        dedupes client runtime injection across renders in the scope,
        and optionally sets a load context for reactive ``load()`` calls.

        Usage:
            with Registry.request_scope():
                # components registered here won't persist
        """
        from contextlib import ExitStack

        from pyjinhx.assets import _runtime_injected
        from pyjinhx.client import ClientBackend
        from pyjinhx.cache import LoadCache
        from pyjinhx.context import PjxContext
        from pyjinhx.dev import warn_mutations_without_render
        from pyjinhx.mutations import MutationTracker

        MutationTracker.clear()
        LoadCache.init_request()
        token = _registry_context.set({})
        runtime_token = _runtime_injected.set(False)
        try:
            with ExitStack() as stack:
                if load_context is not None:
                    stack.enter_context(PjxContext.bind(load_context))
                if client_backend is not None:
                    stack.enter_context(ClientBackend.scope(client_backend))
                yield
        finally:
            warn_mutations_without_render()
            MutationTracker.clear()
            LoadCache.reset_request()
            _runtime_injected.reset(runtime_token)
            _registry_context.reset(token)
