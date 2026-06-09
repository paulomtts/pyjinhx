from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from markupsafe import Markup

from pyjinhx.core.registry import Registry
from pyjinhx.core.renderer import Renderer
from pyjinhx.reactive.keys import ReactiveKey, coerce_reactive_keys
from pyjinhx.utils import css_attribute_selector_attr_value, stamp_root_attributes

from .client import MountedManifest
from .cache import LoadCache


@dataclass
class _Candidate:
    """A dependency-matched region that has been reloaded and rendered."""

    id: str
    html: str
    fresh_hash: str | None
    reported_hash: str | None
    delete: bool = False


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


def _oob_delete_selector(component_id: str) -> str:
    escaped_id = css_attribute_selector_attr_value(component_id)
    return f"delete:[data-pjx-id='{escaped_id}']"


def _manifest_load_arg(entry: dict[str, Any]) -> str | None:
    load = entry.get("load")
    if load is None:
        return None
    return str(load)


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
        load_arg = _manifest_load_arg(entry)
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
        if keyed and load_arg is None:
            continue
        if not keyed:
            load_arg = None

        static_keys = set(getattr(component_class, "_pjx_reacts_to", frozenset()))
        if not (static_keys & dirtied_keys):
            continue

        dedup_key = (component_type, load_arg)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        reported_hash = entry.get("hash")
        try:
            if keyed and load_arg is not None:
                instance = component_class.load(load_arg)
            else:
                instance = component_class.load()
        except LookupError:
            candidates.append(
                _Candidate(
                    id=component_id,
                    html="",
                    fresh_hash=None,
                    reported_hash=reported_hash,
                    delete=True,
                )
            )
            continue

        instance.id = component_id
        fresh_hash = instance.state_hash()
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

    fragments: list[str] = []
    for candidate in surviving:
        if candidate.delete:
            fragments.append(
                f'<div hx-swap-oob="{_oob_delete_selector(candidate.id)}"></div>'
            )
        else:
            fragments.append(
                stamp_root_attributes(
                    candidate.html, {"hx-swap-oob": _oob_swap_selector(candidate.id)}
                )
            )
    return Markup("\n".join(fragments))
