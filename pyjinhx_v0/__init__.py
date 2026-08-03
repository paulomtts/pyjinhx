"""pyjinhx_v0 public API.

Import what you need from the top-level package. Advanced/internal building
blocks (cache internals, manifest parsing, asset-resolver helpers, dev tooling,
``oob_swaps``, …) live in their submodules — e.g. ``from pyjinhx_v0.cache import
LoadCache`` — and are not part of this curated surface.
"""

from pyjinhx_v0.assets import AssetMode
from pyjinhx_v0.base import BaseComponent, Children, Slot, component
from pyjinhx_v0.config import PjxSettings, setup
from pyjinhx_v0.context import PjxContext
from pyjinhx_v0.keys import MutationKey, reactive_key
from pyjinhx_v0.mutations import dirty, mutates
from pyjinhx_v0.reactive import PjxKey, ReactiveComponent
from pyjinhx_v0.registry import Registry
from pyjinhx_v0.renderer import Renderer

__all__ = [  # noqa: RUF022 (grouped by category, not alphabetical, on purpose)
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
