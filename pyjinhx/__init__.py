"""pyjinhx public API.

Import what you need from the top-level package. Advanced/internal building
blocks (cache internals, manifest parsing, asset-resolver helpers, dev tooling,
``oob_swaps``, …) live in their submodules — e.g. ``from pyjinhx.cache import
LoadCache`` — and are not part of this curated surface.
"""

from pyjinhx.assets import AssetMode
from pyjinhx.base import BaseComponent
from pyjinhx.cache import CacheScope
from pyjinhx.client import client_script
from pyjinhx.config import PjxSettings, setup
from pyjinhx.context import PjxContext
from pyjinhx.keys import MutationKey
from pyjinhx.mutations import mutates
from pyjinhx.reactive import PjxKey, ReactiveComponent
from pyjinhx.registry import Registry
from pyjinhx.renderer import Renderer

__all__ = [
    # Components & rendering
    "BaseComponent",
    "ReactiveComponent",
    "Renderer",
    # App wiring
    "setup",
    "Registry",
    # Reactive authoring
    "mutates",
    "MutationKey",
    "PjxKey",
    "PjxContext",
    # Configuration
    "PjxSettings",
    "CacheScope",
    "AssetMode",
    # Runtime
    "client_script",
]
