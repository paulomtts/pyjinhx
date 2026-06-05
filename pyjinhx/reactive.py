from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from markupsafe import Markup

from .base import BaseComponent
from .registry import Registry
from .renderer import Renderer
from .utils import read_client_runtime, stamp_root_attributes

logger = logging.getLogger("pyjinhx")

PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Name of the HTTP header carrying the client's mounted-region manifest."""


def client_script() -> Markup:
    """
    Return the pyjinhx client runtime wrapped in a ``<script>`` tag.

    Drop this into a page shell (e.g. a raw Jinja layout) to emit the
    ``X-PJX-Mounted`` manifest header on every htmx request. When the page shell
    subclasses ``Layout`` the runtime is injected automatically and you do not
    need to call this.
    """
    return Markup(f"<script>{read_client_runtime()}</script>")


class Layout(BaseComponent):
    """
    Base class for full-page shells.

    Rendering a ``Layout`` subclass as the page root injects the pyjinhx client
    runtime once, so mounted reactive regions report their manifest via the
    ``X-PJX-Mounted`` header. Subclass it for your page shell and provide a
    template as usual; fragment endpoints render ordinary components, so the
    runtime is never injected into partial responses.
    """


Layout._pjx_layout = True


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
    # Convenience: duck-type a request-like object (e.g. a FastAPI/Starlette
    # Request) and pull the manifest header off it. We deliberately do NOT import
    # FastAPI/Starlette — this stays an optional convenience, never a dependency.
    # Anything without a .headers.get is not request-like and is ignored.
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
    dirtied: set[str],
    mounted: str | list[dict[str, Any]] | object | None,
    *,
    exclude_ids: set[str] | None = None,
) -> Markup:
    """
    Compute out-of-band swap fragments for every mounted reactive region whose
    declared dependencies intersect the dirtied state keys.

    Dependency-filtered and hash-gated (issue #12, implementation order steps
    1-2): a region depending on a dirtied key is reloaded, and an OOB swap is
    emitted only if its freshly computed state hash differs from the hash the
    client reported for it. A matching hash earns permission to skip; a missing
    or mismatched hash always swaps ("when in doubt, swap").

    Args:
        dirtied: The state keys the route mutated (e.g. {"todos"}).
        mounted: The client manifest — a request-like object exposing
            ``.headers.get`` (the X-PJX-Mounted header is duck-typed out without
            importing any web framework), the raw header string, an already-parsed
            list of {"id", "type", "hash"} dicts, or None/"".
        exclude_ids: Mounted ids to skip (e.g. the id of the primary response,
            which is swapped into the main target rather than out-of-band).

    Returns:
        A single Markup of concatenated OOB swap fragments, each carrying
        hx-swap-oob. Empty Markup if nothing needs swapping.
    """
    manifest = _parse_mounted(mounted)
    if not manifest:
        return Markup("")

    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer(inline_js=False, inline_css=False)

    candidates: list[_Candidate] = []
    seen_types: set[str] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        if not component_type or not component_id:
            continue
        if exclude_ids and component_id in exclude_ids:
            continue

        component_class = classes.get(component_type)
        if component_class is None:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue
        if not (getattr(component_class, "_pjx_depends_on", frozenset()) & dirtied):
            continue

        if component_type in seen_types:
            logger.warning(
                "Multiple mounted instances of reactive type %s; the v1 "
                "type-singleton model reloads it once. Instance-keyed deps are "
                "deferred.",
                component_type,
            )
            continue
        seen_types.add(component_type)

        instance = component_class.load()
        instance.id = component_id
        html = str(instance._render(_renderer=renderer))
        candidates.append(
            _Candidate(
                id=component_id,
                html=html,
                fresh_hash=instance.state_hash(),
                reported_hash=entry.get("hash"),
            )
        )

    # Hash-gate first: skip only regions whose freshly computed state hash exactly
    # matches the hash the client reported (its DOM value is already current).
    # Missing/unknown/mismatched all fall through to a swap ("when in doubt, swap").
    # Gating before dedup ensures an unchanged parent never suppresses a changed child.
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
