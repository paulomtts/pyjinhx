"""pyjinhx public API.

Import what you need from the top-level package. Advanced/internal building
blocks (cache internals, manifest parsing, asset-resolver helpers, dev tooling,
``oob_swaps``, …) live in their submodules — e.g. ``from pyjinhx.cache import
LoadCache`` — and are not part of this curated surface.
"""

from pyjinhx.assets import AssetMode
from pyjinhx.base import BaseComponent, Children, Slot, component
from pyjinhx.config import PjxSettings, setup
from pyjinhx.context import PjxContext
from pyjinhx.keys import MutationKey, reactive_key
from pyjinhx.mutations import dirty, mutates
from pyjinhx.reactive import PjxKey, ReactiveComponent
from pyjinhx.registry import Registry
from pyjinhx.renderer import Renderer

__all__ = [
    # Components & rendering
    "BaseComponent",
    "Slot",
    "Children",
    "component",
    "ReactiveComponent",
    "Renderer",
    # App wiring
    "setup",
    "Registry",
    # Reactive authoring
    "mutates",
    "dirty",
    "MutationKey",
    "reactive_key",
    "PjxKey",
    "PjxContext",
    # Configuration
    "PjxSettings",
    "AssetMode",
]
