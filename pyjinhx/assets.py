from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal

from .finder import Finder
from .utils import (
    component_resolution_classes,
    pascal_case_to_kebab_case,
    read_client_runtime,
)

if TYPE_CHECKING:
    from .base import BaseComponent

AssetKind = Literal["js", "css"]
AssetUrlResolver = Callable[[str], str]

logger = logging.getLogger("pyjinhx")

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
        rendering: Registry keys (``"TypeName_id"`` tuples) of components
            currently on the render stack, used to break cross-reference
            cycles (a same-type-and-id reference renders empty and logs a
            warning).
    """

    assets: list[CollectedAsset] = field(default_factory=list)
    collected_paths: set[str] = field(default_factory=set)
    scripts: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    runtime_injected: bool = False
    rendering: set[tuple[str, str]] = field(default_factory=set)

    def manifest(self, *, resolver: AssetUrlResolver) -> AssetManifest:
        stylesheets: list[str] = []
        scripts: list[str] = []
        for asset in self.assets:
            url = resolver(asset.path)
            if asset.kind == "css":
                stylesheets.append(url)
            else:
                scripts.append(url)
        return AssetManifest(
            stylesheets=tuple(stylesheets),
            scripts=tuple(scripts),
        )


@dataclass(frozen=True)
class AssetManifest:
    stylesheets: tuple[str, ...]
    scripts: tuple[str, ...]


@dataclass(frozen=True)
class AssetPolicy:
    """How a render emits assets: per-kind mode, URL resolution, and dedup."""

    js_mode: AssetMode
    css_mode: AssetMode
    resolve_url: AssetUrlResolver
    loaded_assets: frozenset[str] = frozenset()
    dedup_enabled: bool = False

    def mode(self, kind: AssetKind) -> AssetMode:
        return self.js_mode if kind == "js" else self.css_mode


def runtime_asset_path() -> str:
    """Return the absolute path to the bundled pyjinhx client runtime."""
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "runtime", "pjx.js")
    )


def default_asset_url(path: str, *, root: str) -> str:
    normalized_path = os.path.normpath(path)
    if normalized_path == os.path.normpath(runtime_asset_path()):
        return DEFAULT_RUNTIME_URL
    relative_path = os.path.relpath(normalized_path, root).replace("\\", "/")
    return f"{DEFAULT_STATIC_PREFIX}/{relative_path}"


def make_default_asset_url_resolver(root: str) -> AssetUrlResolver:
    def resolve(path: str) -> str:
        return default_asset_url(path, root=root)

    return resolve


_hash_filename_cache: dict[tuple[str, float], str] = {}


def hashed_filename(path: str, *, hash_len: int = 8) -> str:
    """Return a cache-busted filename such as ``button.a1b2c3d4.js``."""
    normalized_path = os.path.normpath(path)
    mtime = os.path.getmtime(normalized_path)
    cache_key = (normalized_path, mtime, hash_len)
    cached = _hash_filename_cache.get(cache_key)
    if cached is not None:
        return cached
    with open(normalized_path, "rb") as asset_file:
        digest = hashlib.sha256(asset_file.read()).hexdigest()[:hash_len]
    base_name, extension = os.path.splitext(os.path.basename(normalized_path))
    result = f"{base_name}.{digest}{extension}"
    _hash_filename_cache[cache_key] = result
    return result


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
    return session.manifest(resolver=resolver)


def normalize_asset_path(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/")


def register_asset(
    session: RenderSession,
    path: str,
    kind: AssetKind,
    mode: AssetMode,
) -> None:
    normalized_path = normalize_asset_path(path)
    if normalized_path in session.collected_paths:
        return

    if mode == AssetMode.INLINE:
        with open(normalized_path, encoding="utf-8") as asset_file:
            content = asset_file.read()
        if not content:
            return
        if kind == "js":
            session.scripts.append(content)
        else:
            session.styles.append(content)
    elif mode == AssetMode.REFERENCE:
        if not os.path.isfile(normalized_path):
            return
        if os.path.getsize(normalized_path) == 0:
            return
    else:
        return

    session.collected_paths.add(normalized_path)
    session.assets.append(CollectedAsset(path=normalized_path, kind=kind))


def collect_component_asset(
    component: BaseComponent,
    session: RenderSession,
    kind: AssetKind,
    *,
    policy: AssetPolicy,
    component_dir: str | None = None,
    asset_name: str | None = None,
) -> None:
    mode = policy.mode(kind)
    if mode == AssetMode.NONE:
        return

    if component_dir or asset_name:
        candidates = [
            (
                component_dir or Finder.get_class_directory(type(component)),
                asset_name or pascal_case_to_kebab_case(type(component).__name__),
            )
        ]
    else:
        candidates = [
            (Finder.get_class_directory(klass), pascal_case_to_kebab_case(klass.__name__))
            for klass in component_resolution_classes(type(component))
        ]

    for directory, name in candidates:
        asset_path = Finder.find_in_directory(directory, f"{name}.{kind}")
        if asset_path:
            register_asset(session, asset_path, kind, mode)
            return


def collect_extra_assets(
    component: BaseComponent,
    session: RenderSession,
    kind: AssetKind,
    *,
    policy: AssetPolicy,
) -> None:
    mode = policy.mode(kind)
    if mode == AssetMode.NONE:
        return

    extra_paths = component.js if kind == "js" else component.css
    label = "JS" if kind == "js" else "CSS"
    for asset_path in extra_paths:
        normalized_path = normalize_asset_path(asset_path)
        if not os.path.exists(normalized_path):
            logger.warning(
                "Extra %s file not found: %s (component %s, id=%s)",
                label,
                normalized_path,
                type(component).__name__,
                component.id,
            )
            continue
        register_asset(session, normalized_path, kind, mode)


def inject_runtime(
    session: RenderSession,
    *,
    policy: AssetPolicy,
    client: object | None = None,
) -> None:
    from pyjinhx.client import MountedManifest

    if session.runtime_injected:
        return
    if MountedManifest.is_present(client):
        return
    if policy.js_mode == AssetMode.INLINE:
        session.scripts.insert(0, read_client_runtime())
    elif policy.js_mode == AssetMode.REFERENCE:
        runtime_path = normalize_asset_path(runtime_asset_path())
        if runtime_path not in session.collected_paths:
            session.collected_paths.add(runtime_path)
            session.assets.insert(0, CollectedAsset(path=runtime_path, kind="js"))
    session.runtime_injected = True


def should_emit_reference_url(
    url: str,
    loaded_assets: frozenset[str],
    *,
    dedup_enabled: bool,
) -> bool:
    if not dedup_enabled:
        return True
    if not loaded_assets:
        return True
    return url not in loaded_assets


def render_assets(session: RenderSession, kind: AssetKind, *, policy: AssetPolicy) -> str:
    mode = policy.mode(kind)
    if mode == AssetMode.INLINE:
        items = session.scripts if kind == "js" else session.styles
        if not items:
            return ""
        if kind == "js":
            return "\n".join(f"<script>{script}</script>" for script in items)
        return "\n".join(f"<style>{style}</style>" for style in items)
    if mode == AssetMode.REFERENCE:
        kind_assets = [asset for asset in session.assets if asset.kind == kind]
        if not kind_assets:
            return ""
        tags: list[str] = []
        for asset in kind_assets:
            url = policy.resolve_url(asset.path)
            if should_emit_reference_url(
                url, policy.loaded_assets, dedup_enabled=policy.dedup_enabled
            ):
                if kind == "js":
                    tags.append(f'<script src="{url}"></script>')
                else:
                    tags.append(f'<link rel="stylesheet" href="{url}">')
        return "\n".join(tags)
    return ""


def apply_component_render_assets(
    component: BaseComponent,
    rendered_markup: str,
    session: RenderSession,
    *,
    template_path: str | None,
    is_root: bool,
    collect_component_js: bool,
    policy: AssetPolicy,
    client: object | None,
) -> str:
    if template_path is not None and type(component).__name__ == "BaseComponent":
        asset_dir: str | None = os.path.dirname(template_path)
        asset_name: str | None = os.path.splitext(os.path.basename(template_path))[
            0
        ].replace("_", "-")
    else:
        asset_dir = None
        asset_name = None

    if collect_component_js:
        collect_component_asset(
            component, session, "js",
            policy=policy, component_dir=asset_dir, asset_name=asset_name,
        )
        collect_component_asset(
            component, session, "css",
            policy=policy, component_dir=asset_dir, asset_name=asset_name,
        )

    # Extra assets (e.g. Dropdown.js = [popover.js]) must be collected for
    # every component in the tree, not just the root, so nested components
    # (e.g. a Dropdown inside a Card) still ship their dependencies.
    collect_extra_assets(component, session, "css", policy=policy)
    collect_extra_assets(component, session, "js", policy=policy)

    if not is_root:
        return rendered_markup

    # Runtime injection and markup injection are root-only.
    if policy.js_mode != AssetMode.NONE:
        inject_runtime(session, policy=policy, client=client)
    if policy.css_mode == AssetMode.NONE and policy.js_mode == AssetMode.NONE:
        return rendered_markup

    return inject_assets(rendered_markup, session, policy=policy)


def inject_assets(markup: str, session: RenderSession, *, policy: AssetPolicy) -> str:
    css_markup = render_assets(session, "css", policy=policy)
    js_markup = render_assets(session, "js", policy=policy)
    if css_markup:
        markup = f"{css_markup}\n{markup}"
    if js_markup:
        markup = f"{markup}\n{js_markup}"
    return markup
