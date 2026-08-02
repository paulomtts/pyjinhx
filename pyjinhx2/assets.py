"""L2.2 assets — delivery modes, emission, and the manifest of a request's assets."""

import hashlib
import os
from collections.abc import Callable, Iterable
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
    # One member for both kinds: the asset kind already decides the tag shape
    # (<link rel="stylesheet"> vs <script src>), so a separate SRC member would
    # only create a way to set the wrong one on the wrong kind.
    LINK = "link"


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


def _sorted_resolved(
    paths: Iterable[Path], resolver: Callable[[Path], str]
) -> tuple[str, ...]:
    """Return the URLs for the given asset paths, in path-sorted order.

    Sorted before resolving because the accumulator stores paths in a set,
    which has no stable iteration order, and two renders of the same tree must
    produce byte-identical output. A resolver that raises is left to raise — an
    asset silently dropped from the page fails invisibly in the browser.
    """
    return tuple(resolver(path) for path in sorted(paths, key=str))


def _url_tags(
    paths: set[Path], resolver: Callable[[Path], str], template: str
) -> list[str]:
    """Format each resolved asset URL into the given tag, in path-sorted order."""
    return [template.format(url=url) for url in _sorted_resolved(paths, resolver)]


def _require_resolver(
    resolver: Callable[[Path], str] | None,
) -> Callable[[Path], str]:
    """Return the resolver, refusing to emit LINK tags without one.

    Raising rather than skipping the kind: a page quietly missing its
    stylesheets is harder to diagnose than a failed render.
    """
    if resolver is None:
        raise ValueError("LINK mode needs a resolver to build asset URLs")
    return resolver


def emit_assets(
    session: "RenderSession", *, resolver: Callable[[Path], str] | None = None
) -> str:
    """Return the markup for this session's accumulated assets, per delivery mode.

    Args:
        session: The RenderSession whose css_assets/js_assets were populated by
            accumulate_assets during the render, and whose css_mode/js_mode say
            how each kind is delivered.
        resolver: Maps an asset path to the URL it is served from, in the shape
            asset_manifest() takes. Required only when a kind is in LINK mode.

    Returns:
        Concatenated CSS tags then JS tags, newline-joined, with the session's
        inline runtime script (if any) leading the JS tags. Empty string when
        both kinds are NONE or nothing was accumulated.

    Raises:
        OSError: If an asset file is missing or unreadable under INLINE mode.
        ValueError: If a kind is in LINK mode and no resolver was given.
    """
    tags: list[str] = []
    if session.css_mode is AssetMode.INLINE:
        tags += _inline_tags(session.css_assets, "<style>", "</style>")
    elif session.css_mode is AssetMode.LINK:
        tags += _url_tags(
            session.css_assets,
            _require_resolver(resolver),
            '<link rel="stylesheet" href="{url}">',
        )
    if session.js_mode is AssetMode.INLINE:
        # Runtime first: component scripts may call into pjx/htmx as soon as
        # they execute, so the tag that defines them has to precede them.
        if session.runtime_script is not None:
            tags.append(session.runtime_script)
        tags += _inline_tags(session.js_assets, "<script>", "</script>")
    elif session.js_mode is AssetMode.LINK:
        tags += _url_tags(
            session.js_assets,
            _require_resolver(resolver),
            '<script src="{url}"></script>',
        )
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
        stylesheets=_sorted_resolved(session.css_assets, resolver),
        scripts=_sorted_resolved(session.js_assets, resolver),
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


def asset_token(path: Path) -> str:
    """Return the opaque dedup token the client reports for this asset.

    The identity the ``data-pjx-asset`` attribute carries and ``X-PJX-Assets``
    reports back, so the server can tell an asset the browser already has from
    one it does not. Derived from the normalized path rather than the file's
    contents: an edited asset must keep the same identity, or every reactive
    response after an edit would append a second copy to the head instead of
    recognizing the one already there.
    """
    normalized = os.path.normpath(str(path)).replace("\\", "/")
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def resolver_with_hash(base_url: str, root: str) -> Callable[[Path], str]:
    """Build an asset resolver that embeds a content hash in each filename.

    The returned callable has the shape asset_manifest expects for its
    resolver, so a caller wires cache-busted URLs in with one argument.

    Args:
        base_url: URL prefix the asset tree is served from; a trailing slash
            is ignored.
        root: Directory the asset paths are laid out under; the part of a
            path below it is preserved in the URL.

    Returns:
        A callable mapping an asset path to its hashed URL, which raises
        OSError if the file is missing.
    """

    def resolve(path: Path) -> str:
        relative_dir = path.parent.relative_to(root)
        hashed = hashed_filename(path)
        prefix = base_url.rstrip("/")
        # relative_to returns Path(".") for a file sitting directly in root,
        # which would otherwise render as a "/./" segment in the URL.
        if relative_dir == Path("."):
            return f"{prefix}/{hashed}"
        return f"{prefix}/{relative_dir.as_posix()}/{hashed}"

    return resolve


def _all_component_classes(root: type) -> set[type]:
    """Every class below root in the subclass tree, root excluded.

    Recursive rather than one level deep: a component that subclasses another
    component is a distinct class with its own descriptor, and only leaves of
    a deep hierarchy would be seen otherwise. Returned as a set because
    multiple inheritance makes a class reachable by more than one path.
    """
    found: set[type] = set()
    for subclass in root.__subclasses__():
        found.add(subclass)
        found |= _all_component_classes(subclass)
    return found


def all_assets() -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Return every CSS and JS path declared by any component class.

    Registry-wide rather than session-scoped: a class contributes its assets
    whether or not it was rendered, which is what a build step bundling the
    whole asset tree needs, as opposed to asset_manifest's per-request view.

    Only classes imported by the time of the call are visible, since Python
    discovers subclasses as their modules execute — import the component
    package before calling this from a build script.

    Returns:
        The CSS paths then the JS paths, each deduped and in path-sorted
        order so repeated calls and repeated builds agree byte for byte.
    """
    # Imported here rather than at module scope: session imports this module
    # and component imports session, so a top-level import would cycle.
    from pyjinhx2.component import BaseComponent

    css: set[Path] = set()
    js: set[Path] = set()
    for cls in _all_component_classes(BaseComponent):
        # A class that never went through descriptor resolution — an abstract
        # mixin, say — has no descriptor attribute at all, and contributes
        # nothing rather than failing the whole enumeration.
        descriptor = getattr(cls, "__pjx_descriptor__", None)
        if descriptor is None:
            continue
        css.update(descriptor.css_paths)
        js.update(descriptor.js_paths)
    return tuple(sorted(css, key=str)), tuple(sorted(js, key=str))
