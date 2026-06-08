from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from markupsafe import Markup

from pyjinhx.core.registry import Registry
from pyjinhx.core.renderer import Renderer
from pyjinhx.reactive.keys import (
    ReactiveKey,
    coerce_reactive_keys,
    interpolate_reactive_keys,
)
from pyjinhx.utils import css_attribute_selector_attr_value, stamp_root_attributes

from .load_cache import LoadCache
from .payload import MountedManifest


@dataclass
class _Candidate:
    """A dependency-matched region that has been reloaded and rendered."""

    id: str
    html: str
    fresh_hash: str
    reported_hash: str | None


def _drop_nested(candidates: list[_Candidate]) -> list[_Candidate]:
    """
    Drop any candidate whose data-pjx-id marker appears inside another candidate's
    HTML — the parent's fresh HTML already contains the child, so a separate swap
    would be redundant (and would fight the parent's swap).
    """
    markers = {
        candidate.id: f'data-pjx-id="{candidate.id}"' for candidate in candidates
    }
    html_by_id = {candidate.id: candidate.html for candidate in candidates}
    surviving: list[_Candidate] = []
    for candidate in candidates:
        marker = markers[candidate.id]
        nested_in_other = any(
            marker in html_by_id[other.id]
            for other in candidates
            if other.id != candidate.id
        )
        if not nested_in_other:
            surviving.append(candidate)
    return surviving


def _oob_swap_selector(component_id: str) -> str:
    escaped_id = css_attribute_selector_attr_value(component_id)
    return f"outerHTML:[data-pjx-id='{escaped_id}']"


def oob_swaps(
    dirtied: set[ReactiveKey],
    mounted: str | list[dict[str, Any]] | object | None,
    *,
    exclude_ids: set[str] | None = None,
    skip_invalidate: bool = False,
) -> Markup:
    """
    Compute out-of-band swap fragments for every mounted reactive region whose
    declared dependencies intersect the dirtied state keys.
    """
    dirtied_keys = coerce_reactive_keys(dirtied)
    if not skip_invalidate:
        LoadCache.invalidate(dirtied_keys)

    manifest = MountedManifest.parse(mounted)
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

        static_keys = interpolate_reactive_keys(
            getattr(component_class, "_pjx_reacts_to", frozenset()),
            skey,
            keyed=keyed,
        )
        if not (static_keys & dirtied_keys):
            continue

        dedup_key = (component_type, skey)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        instance = component_class.load(skey) if keyed else component_class.load()
        if not (instance.effective_reacts_to() & dirtied_keys):
            continue
        instance.id = component_id
        fresh_hash = instance.state_hash()
        reported_hash = entry.get("hash")
        if fresh_hash == reported_hash:
            continue
        html = str(instance._render(_renderer=renderer, emit_assets=False))
        candidates.append(
            _Candidate(
                id=component_id,
                html=html,
                fresh_hash=fresh_hash,
                reported_hash=reported_hash,
            )
        )

    surviving = _drop_nested(candidates)
    if not surviving:
        return Markup("")

    fragments = [
        stamp_root_attributes(
            c.html, {"hx-swap-oob": _oob_swap_selector(c.id)}
        )
        for c in surviving
    ]
    return Markup("\n".join(fragments))
