"""L2.2 assets — delivery modes, emission, and the manifest of a request's assets."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
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
    return [
        f"{open_tag}{path.read_text()}{close_tag}" for path in sorted(paths, key=str)
    ]


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


@dataclass(frozen=True)
class AssetManifest:
    """The resolved asset URLs for one render, split by kind.

    Attributes:
        stylesheets: URLs of the render's CSS assets, in path order.
        scripts: URLs of the render's JS assets, in path order.
    """

    stylesheets: tuple[str, ...]
    scripts: tuple[str, ...]


def _resolved_urls(
    paths: set[Path], resolver: Callable[[Path], str]
) -> tuple[str, ...]:
    """Resolve each path to a URL, sorted by path for a stable order.

    Sorted for the same reason _inline_tags sorts: the accumulator is a set,
    and two renders of the same tree must produce the same manifest. A
    resolver that raises is left to raise — a manifest missing one asset is a
    page missing one stylesheet, which fails silently in the browser.
    """
    return tuple(resolver(path) for path in sorted(paths, key=str))


def asset_manifest(
    session: "RenderSession", *, resolver: Callable[[Path], str]
) -> AssetManifest:
    """Return the resolved URLs of this session's accumulated assets.

    Kinds stay in separate tuples so a caller builds <link> and <script src>
    tags without re-inspecting file extensions. Independent of css_mode/
    js_mode: those govern emit_assets, not what the render used.

    Args:
        session: The RenderSession whose css_assets/js_assets were populated
            by accumulate_assets during the render.
        resolver: Maps an asset path to the URL it is served from.

    Returns:
        An AssetManifest of CSS then JS URLs, each in path-sorted order.
    """
    return AssetManifest(
        stylesheets=_resolved_urls(session.css_assets, resolver),
        scripts=_resolved_urls(session.js_assets, resolver),
    )


_hash_filename_cache: dict[tuple[str, float, int], str] = {}


def hashed_filename(path: Path, *, hash_len: int = 8) -> str:
    """Return a cache-busted filename such as ``button.a1b2c3d4.js``.

    Args:
        path: The asset file on disk to hash.
        hash_len: How many hex characters of the SHA-256 digest to keep.

    Returns:
        The file's stem, the truncated digest, and its suffix, dot-joined.

    Raises:
        OSError: If the file is missing or unreadable.
    """
    # Keyed on mtime as well as path so an edited asset re-hashes, while a
    # repeated render of an untouched tree never re-reads the file.
    key = (str(path.resolve()), path.stat().st_mtime, hash_len)
    cached = _hash_filename_cache.get(key)
    if cached is not None:
        return cached
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:hash_len]
    result = f"{path.stem}.{digest}{path.suffix}"
    _hash_filename_cache[key] = result
    return result
