"""L2.2.2 assets — delivery modes and emission of a request's accumulated assets."""

from enum import Enum


class AssetMode(str, Enum):
    """How a kind of asset reaches the page for one render."""

    INLINE = "inline"
    NONE = "none"
