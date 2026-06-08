from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from markupsafe import Markup

from pyjinhx.core.assets import DEFAULT_RUNTIME_URL, AssetMode
from pyjinhx.core.registry import Registry
from pyjinhx.core.renderer import Renderer
from pyjinhx.utils import (
    ReactiveKey,
    coerce_reactive_keys,
    interpolate_reactive_keys,
    read_client_runtime,
    stamp_root_attributes,
)

from .cache import invalidate

logger = logging.getLogger("pyjinhx")

PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Name of the HTTP header carrying the client's mounted-region manifest."""

PJX_ASSETS_HEADER = "X-PJX-Assets"
"""Name of the HTTP header carrying asset URLs already loaded in the browser."""


def client_script(
    *,
    mode: AssetMode | None = None,
    src: str | None = None,
) -> Markup:
    """
    Return the pyjinhx client runtime as a ``<script>`` tag.

    Drop this into a raw Jinja page shell when you are not rendering through a
    root ``BaseComponent.render()`` call. Root full-page renders inject the
    runtime automatically unless the request already carries ``X-PJX-Mounted``.

    Args:
        mode: ``AssetMode.INLINE`` (default) inlines the runtime source.
            ``AssetMode.REFERENCE`` emits ``<script src="...">``.
        src: Public URL for the runtime when ``mode`` is ``AssetMode.REFERENCE``.
            Defaults to ``Renderer``'s configured runtime URL.
    """
    effective_mode = mode or AssetMode.INLINE
    if effective_mode == AssetMode.REFERENCE:
        runtime_url = src or Renderer._default_runtime_url or DEFAULT_RUNTIME_URL
        return Markup(f'<script src="{runtime_url}"></script>')
    return Markup(f"<script>{read_client_runtime()}</script>")


@dataclass
class _Candidate:
    """A dependency-matched region that has been reloaded and rendered."""

    id: str
    html: str
    fresh_hash: str
    reported_hash: str | None


def _parse_mounted(
    mounted: str | list[dict[str, Any]] | object | None,
) -> list[dict[str, Any]]:
    if mounted is None or mounted == "":
        return []
    if isinstance(mounted, list):
        return mounted
    if isinstance(mounted, str):
        try:
            parsed = json.loads(mounted)
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse %s manifest as JSON; ignoring.", PJX_MOUNTED_HEADER
            )
            return []
        return parsed if isinstance(parsed, list) else []
    try:
        header_value = mounted.headers.get(PJX_MOUNTED_HEADER)
    except AttributeError:
        logger.warning(
            "mounted is not an %s header string, parsed list, request-like "
            "object, or None; ignoring.",
            PJX_MOUNTED_HEADER,
        )
        return []
    return _parse_mounted(header_value)


def parse_loaded_assets(
    client: str | list[str] | object | None,
) -> frozenset[str]:
    """
    Parse the client-reported list of asset URLs already loaded in the browser.

    Accepts a request-like object (``headers.get``), a raw JSON string, a parsed
    list of URLs, or ``None``/``""`` (treated as nothing loaded for dedup purposes).
    """
    if client is None or client == "":
        return frozenset()
    if isinstance(client, (list, tuple, set, frozenset)):
        return frozenset(str(url) for url in client)
    if isinstance(client, str):
        try:
            parsed = json.loads(client)
        except json.JSONDecodeError:
            logger.warning("Could not parse %s as JSON; ignoring.", PJX_ASSETS_HEADER)
            return frozenset()
        if isinstance(parsed, list):
            return frozenset(str(url) for url in parsed)
        return frozenset()
    try:
        header_value = client.headers.get(PJX_ASSETS_HEADER)
    except AttributeError:
        return frozenset()
    return parse_loaded_assets(header_value)


def client_has_mounted_manifest(
    client: str | list[dict[str, Any]] | object | None,
) -> bool:
    """
    Return whether the client already sent a valid ``X-PJX-Mounted`` manifest.

    A present header whose value parses to a JSON array (including ``[]``)
    means ``pjx.js`` is active in the browser. Missing, empty, or malformed
    values mean the runtime should be injected on root full-page renders.
    """
    if client is None:
        return False
    if isinstance(client, list):
        return True
    if isinstance(client, str):
        if client == "":
            return False
        try:
            parsed = json.loads(client)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, list)
    try:
        header_value = client.headers.get(PJX_MOUNTED_HEADER)
    except AttributeError:
        return False
    return client_has_mounted_manifest(header_value)


def _drop_nested(candidates: list[_Candidate]) -> list[_Candidate]:
    """
    Drop any candidate whose data-pjx-id marker appears inside another candidate's
    HTML — the parent's fresh HTML already contains the child, so a separate swap
    would be redundant (and would fight the parent's swap).

    Runs only over regions that are actually being swapped (post hash-gate), so an
    unchanged parent never suppresses a changed child.
    """
    surviving: list[_Candidate] = []
    for index, candidate in enumerate(candidates):
        marker = f'data-pjx-id="{candidate.id}"'
        nested_in_other = any(
            marker in other.html
            for other_index, other in enumerate(candidates)
            if other_index != index
        )
        if not nested_in_other:
            surviving.append(candidate)
    return surviving


def oob_swaps(
    dirtied: set[ReactiveKey],
    mounted: str | list[dict[str, Any]] | object | None,
    *,
    exclude_ids: set[str] | None = None,
) -> Markup:
    """
    Compute out-of-band swap fragments for every mounted reactive region whose
    declared dependencies intersect the dirtied state keys.
    """
    dirtied_keys = coerce_reactive_keys(dirtied)
    invalidate(dirtied_keys)

    manifest = _parse_mounted(mounted)
    if not manifest:
        return Markup("")

    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer()

    candidates: list[_Candidate] = []
    seen: set[tuple[str, str | None]] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        key = entry.get("key")
        skey = str(key) if key is not None else None
        if not component_type or not component_id:
            continue
        if exclude_ids and component_id in exclude_ids:
            continue

        component_class = classes.get(component_type)
        if component_class is None:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue

        keyed = getattr(component_class, "_pjx_keyed", False)
        if keyed and skey is None:
            continue
        if not keyed:
            skey = None

        effective = interpolate_reactive_keys(
            getattr(component_class, "_pjx_reacts_to", frozenset()),
            skey,
            keyed=keyed,
        )
        if not (effective & dirtied_keys):
            continue

        dedup_key = (component_type, skey)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        instance = component_class.load(skey) if keyed else component_class.load()
        instance.id = component_id
        html = str(instance._render(_renderer=renderer, emit_assets=False))
        candidates.append(
            _Candidate(
                id=component_id,
                html=html,
                fresh_hash=instance.state_hash(),
                reported_hash=entry.get("hash"),
            )
        )

    changed = [c for c in candidates if c.fresh_hash != c.reported_hash]

    surviving = _drop_nested(changed)
    if not surviving:
        return Markup("")

    fragments = [
        stamp_root_attributes(
            c.html, {"hx-swap-oob": f"outerHTML:[data-pjx-id='{c.id}']"}
        )
        for c in surviving
    ]
    return Markup("\n".join(fragments))
