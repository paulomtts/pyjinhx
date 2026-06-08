from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from .assets import (
    AssetKind,
    AssetMode,
    CollectedAsset,
    RenderSession,
    runtime_asset_path,
)
from .finder import Finder
from ..utils import pascal_case_to_kebab_case, read_client_runtime

if TYPE_CHECKING:
    from .base import BaseComponent

logger = logging.getLogger("pyjinhx")


def normalize_asset_path(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/")


def asset_mode(js_mode: AssetMode, css_mode: AssetMode, kind: AssetKind) -> AssetMode:
    return js_mode if kind == "js" else css_mode


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
    js_mode: AssetMode,
    css_mode: AssetMode,
    component_dir: str | None = None,
    asset_name: str | None = None,
) -> None:
    mode = asset_mode(js_mode, css_mode, kind)
    if mode == AssetMode.NONE:
        return

    component_directory = component_dir or Finder.get_class_directory(type(component))
    name = asset_name or pascal_case_to_kebab_case(type(component).__name__)
    asset_filename = f"{name}.{kind}"
    asset_path = Finder.find_in_directory(component_directory, asset_filename)
    if not asset_path:
        return

    register_asset(session, asset_path, kind, mode)


def collect_extra_assets(
    component: BaseComponent,
    session: RenderSession,
    kind: AssetKind,
    *,
    js_mode: AssetMode,
    css_mode: AssetMode,
) -> None:
    mode = asset_mode(js_mode, css_mode, kind)
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
    js_mode: AssetMode,
    client: object | None = None,
) -> None:
    from pyjinhx.reactive.payload import MountedManifest

    if session.runtime_injected:
        return
    if MountedManifest.is_present(client):
        return
    if js_mode == AssetMode.INLINE:
        session.scripts.insert(0, read_client_runtime())
    elif js_mode == AssetMode.REFERENCE:
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


def render_assets(
    session: RenderSession,
    kind: AssetKind,
    *,
    js_mode: AssetMode,
    css_mode: AssetMode,
    resolve_url: Callable[[str], str],
    loaded_assets: frozenset[str] = frozenset(),
    dedup_enabled: bool = False,
) -> str:
    mode = asset_mode(js_mode, css_mode, kind)
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
            url = resolve_url(asset.path)
            if should_emit_reference_url(
                url, loaded_assets, dedup_enabled=dedup_enabled
            ):
                if kind == "js":
                    tags.append(f'<script src="{url}"></script>')
                else:
                    tags.append(f'<link rel="stylesheet" href="{url}">')
        return "\n".join(tags)
    return ""


def inject_assets(
    markup: str,
    session: RenderSession,
    *,
    js_mode: AssetMode,
    css_mode: AssetMode,
    resolve_url: Callable[[str], str],
    loaded_assets: frozenset[str] = frozenset(),
    dedup_enabled: bool = False,
) -> str:
    css_markup = render_assets(
        session,
        "css",
        js_mode=js_mode,
        css_mode=css_mode,
        resolve_url=resolve_url,
        loaded_assets=loaded_assets,
        dedup_enabled=dedup_enabled,
    )
    js_markup = render_assets(
        session,
        "js",
        js_mode=js_mode,
        css_mode=css_mode,
        resolve_url=resolve_url,
        loaded_assets=loaded_assets,
        dedup_enabled=dedup_enabled,
    )
    if css_markup:
        markup = f"{css_markup}\n{markup}"
    if js_markup:
        markup = f"{markup}\n{js_markup}"
    return markup
