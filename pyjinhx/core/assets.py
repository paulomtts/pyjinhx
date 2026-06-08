from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

AssetKind = Literal["js", "css"]
AssetUrlResolver = Callable[[str], str]

DEFAULT_RUNTIME_URL = "/static/pyjinhx/pjx.js"
DEFAULT_STATIC_PREFIX = "/static/components"


class AssetMode(str, Enum):
    INLINE = "inline"
    REFERENCE = "reference"
    NONE = "none"


@dataclass
class CollectedAsset:
    path: str
    kind: AssetKind


@dataclass
class RenderSession:
    """
    Per-render state for asset aggregation and deduplication.

    Attributes:
        assets: Ordered, deduplicated asset paths collected during rendering.
        collected_paths: Set of normalized paths already processed.
        scripts: Inline JavaScript payloads (INLINE mode only).
        styles: Inline CSS payloads (INLINE mode only).
        runtime_injected: Whether the pyjinhx client runtime was scheduled.
    """

    assets: list[CollectedAsset] = field(default_factory=list)
    collected_paths: set[str] = field(default_factory=set)
    scripts: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    runtime_injected: bool = False

    def manifest(self, *, resolver: AssetUrlResolver) -> AssetManifest:
        return asset_manifest(self, resolver=resolver)


@dataclass(frozen=True)
class AssetManifest:
    stylesheets: tuple[str, ...]
    scripts: tuple[str, ...]


def runtime_asset_path() -> str:
    """Return the absolute path to the bundled pyjinhx client runtime."""
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "runtime", "pjx.js")
    )


def asset_mode_from_inline(inline: bool) -> AssetMode:
    return AssetMode.INLINE if inline else AssetMode.NONE


def default_asset_url(path: str, *, kind: AssetKind, root: str) -> str:
    normalized_path = os.path.normpath(path)
    if normalized_path == os.path.normpath(runtime_asset_path()):
        return DEFAULT_RUNTIME_URL
    relative_path = os.path.relpath(normalized_path, root).replace("\\", "/")
    return f"{DEFAULT_STATIC_PREFIX}/{relative_path}"


def make_default_asset_url_resolver(root: str) -> AssetUrlResolver:
    def resolve(path: str) -> str:
        kind: AssetKind = "css" if path.lower().endswith(".css") else "js"
        return default_asset_url(path, kind=kind, root=root)

    return resolve


def hashed_filename(path: str, *, hash_len: int = 8) -> str:
    """Return a cache-busted filename such as ``button.a1b2c3d4.js``."""
    with open(path, "rb") as asset_file:
        digest = hashlib.sha256(asset_file.read()).hexdigest()[:hash_len]
    base_name, extension = os.path.splitext(os.path.basename(path))
    return f"{base_name}.{digest}{extension}"


def resolver_with_hash(base_url: str, root: str) -> AssetUrlResolver:
    """Build an asset URL resolver that embeds a content hash in each filename."""

    def resolve(path: str) -> str:
        normalized_path = os.path.normpath(path)
        if normalized_path == os.path.normpath(runtime_asset_path()):
            hashed = hashed_filename(normalized_path)
            return f"{base_url.rstrip('/')}/pyjinhx/{hashed}"
        relative_dir = os.path.relpath(os.path.dirname(normalized_path), root).replace(
            "\\", "/"
        )
        hashed = hashed_filename(normalized_path)
        if relative_dir == ".":
            return f"{base_url.rstrip('/')}/{hashed}"
        return f"{base_url.rstrip('/')}/{relative_dir}/{hashed}"

    return resolve


def asset_manifest(
    session: RenderSession,
    *,
    resolver: AssetUrlResolver,
) -> AssetManifest:
    stylesheets: list[str] = []
    scripts: list[str] = []
    for asset in session.assets:
        url = resolver(asset.path)
        if asset.kind == "css":
            stylesheets.append(url)
        else:
            scripts.append(url)
    return AssetManifest(
        stylesheets=tuple(stylesheets),
        scripts=tuple(scripts),
    )
