"""L2.2.2 assets — delivery modes and emission of a request's accumulated assets."""

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyjinhx2.session import RenderSession


class AssetMode(str, Enum):
    """How a kind of asset reaches the page for one render."""

    INLINE = "inline"
    NONE = "none"


def _inline_tags(paths: set[Path], open_tag: str, close_tag: str) -> list[str]:
    """Read each path and wrap its contents in the given tag pair, sorted by path.

    Sorted because the accumulator stores paths in a set, which has no stable
    iteration order; two renders of the same tree must produce byte-identical
    output. A path that cannot be read raises: an asset silently dropped from
    the page is a styling bug nobody can see in the response.
    """
    return [f"{open_tag}{path.read_text()}{close_tag}" for path in sorted(paths, key=str)]


def emit_assets(session: "RenderSession") -> str:
    """Return the markup for this session's accumulated assets, per delivery mode.

    Args:
        session: The RenderSession whose css_assets/js_assets were populated by
            accumulate_assets during the render, and whose css_mode/js_mode say
            how each kind is delivered.

    Returns:
        Concatenated <style> tags then <script> tags, newline-joined. Empty
        string when both kinds are NONE or nothing was accumulated.

    Raises:
        OSError: If an asset file is missing or unreadable under INLINE mode.
    """
    tags: list[str] = []
    if session.css_mode is AssetMode.INLINE:
        tags += _inline_tags(session.css_assets, "<style>", "</style>")
    if session.js_mode is AssetMode.INLINE:
        tags += _inline_tags(session.js_assets, "<script>", "</script>")
    return "\n".join(tags)
