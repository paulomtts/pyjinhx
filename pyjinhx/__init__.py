"""pyjinhx — server-rendered, htmx-wired components for Python web apps.

This module re-exports the public API; advanced or internal usage lives in the
submodules (`pyjinhx.reactive.keys`, `pyjinhx.reactive.mutations`,
`pyjinhx.registry`, `pyjinhx.rendering`).
"""

from __future__ import annotations

import sys
import types
from typing import Any

__all__ = [  # noqa: RUF022
    # components & rendering
    "BaseComponent",
    "Slot",
    "Children",
    "component",
    "ReactiveComponent",
    "render",
    "RenderSession",
    # app wiring
    "setup",
    "PjxContext",
    # reactive authoring
    "mutates",
    "dirty",
    "MutationKey",
    "reactive_key",
    "PjxKey",
    "AppContext",
    # configuration
    "PjxSettings",
    "AssetMode",
]

_lazy_imports = {
    "BaseComponent": ("pyjinhx.component", "BaseComponent"),
    "Children": ("pyjinhx.component", "Children"),
    "Slot": ("pyjinhx.component", "Slot"),
    "component": ("pyjinhx.classless", "component"),
    "ReactiveComponent": ("pyjinhx.reactive.component", "ReactiveComponent"),
    "render": ("pyjinhx.rendering", "render"),
    "RenderSession": ("pyjinhx.session", "RenderSession"),
    "setup": ("pyjinhx.config", "setup"),
    "PjxContext": ("pyjinhx.context", "PjxContext"),
    "AppContext": ("pyjinhx.app_context", "AppContext"),
    "PjxKey": ("pyjinhx.reactive.component", "PjxKey"),
    "MutationKey": ("pyjinhx.reactive.keys", "MutationKey"),
    "reactive_key": ("pyjinhx.reactive.keys", "reactive_key"),
    "dirty": ("pyjinhx.reactive.mutations", "dirty"),
    "mutates": ("pyjinhx.reactive.mutations", "mutates"),
    "PjxSettings": ("pyjinhx.config", "PjxSettings"),
    "AssetMode": ("pyjinhx.assets", "AssetMode"),
}

_cached_imports = {}


class _PyjinhxModule(types.ModuleType):
    """Custom module that provides lazy-loaded public API."""

    def __getattr__(self, name: str) -> Any:
        """Lazy-load public API exports on demand."""
        if name in _lazy_imports:
            # Check cache first
            if name in _cached_imports:
                return _cached_imports[name]

            module_name, attr_name = _lazy_imports[name]
            module = __import__(module_name, fromlist=[attr_name])
            result = getattr(module, attr_name)

            # Cache the result
            _cached_imports[name] = result
            return result

        raise AttributeError(f"module {self.__name__!r} has no attribute {name!r}")


# Replace this module in sys.modules with the custom class
_current_module = sys.modules[__name__]
_new_module = _PyjinhxModule(__name__)
_new_module.__dict__.update(_current_module.__dict__)
sys.modules[__name__] = _new_module
