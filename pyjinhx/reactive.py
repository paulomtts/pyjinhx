from __future__ import annotations

import json
import logging
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


def _parse_mounted(mounted: str | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
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
    raise TypeError(
        "mounted must be the X-PJX-Mounted header string, a parsed list, or None. "
        "Passing a request object is supported once render() parameterization lands (step 3)."
    )


def _drop_nested(rendered: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Drop any rendered region whose data-pjx-id marker appears inside another
    region's HTML — the parent's fresh HTML already contains the child, so a
    separate swap would be redundant (and would fight the parent's swap).
    """
    surviving: list[tuple[str, str]] = []
    for index, (component_id, html) in enumerate(rendered):
        marker = f'data-pjx-id="{component_id}"'
        nested_in_other = any(
            marker in other_html
            for other_index, (_, other_html) in enumerate(rendered)
            if other_index != index
        )
        if not nested_in_other:
            surviving.append((component_id, html))
    return surviving


def oob_swaps(
    dirtied: set[str],
    mounted: str | list[dict[str, Any]] | None,
) -> Markup:
    """
    Compute out-of-band swap fragments for every mounted reactive region whose
    declared dependencies intersect the dirtied state keys.

    This is the always-swap baseline (issue #12, implementation order step 1):
    every region depending on a dirtied key is reloaded and swapped. Hash-gating
    (skipping regions whose value did not change) is layered on in step 2.

    Args:
        dirtied: The state keys the route mutated (e.g. {"todos"}).
        mounted: The client manifest from the X-PJX-Mounted header — the raw JSON
            string, an already-parsed list of {"id", "type", "hash"} dicts, or
            None/"".

    Returns:
        A single Markup of concatenated OOB swap fragments, each carrying
        hx-swap-oob. Empty Markup if nothing needs swapping.
    """
    manifest = _parse_mounted(mounted)
    if not manifest:
        return Markup("")

    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer(inline_js=False, inline_css=False)

    rendered: list[tuple[str, str]] = []
    seen_types: set[str] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        if not component_type or not component_id:
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
        rendered.append((component_id, str(instance._render(_renderer=renderer))))

    surviving = _drop_nested(rendered)
    if not surviving:
        return Markup("")

    fragments = [
        stamp_root_attributes(
            html, {"hx-swap-oob": f"outerHTML:[data-pjx-id='{component_id}']"}
        )
        for component_id, html in surviving
    ]
    return Markup("\n".join(fragments))
