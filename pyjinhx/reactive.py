from __future__ import annotations

import hashlib
import json
import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from markupsafe import Markup

from .base import BaseComponent
from .cache import invalidate
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
    is marked ``base_layout=True`` the runtime is injected automatically and you
    do not need to call this.
    """
    return Markup(f"<script>{read_client_runtime()}</script>")


class ReactiveComponent(BaseComponent):
    """
    Base class for dependency-aware reactive components.

    A reactive component declares the state keys it derives from (``depends_on``)
    and how to rebuild itself from the current world (``load()``). Both are
    required — ``load()`` is enforced by ABC (you cannot instantiate a subclass
    that does not implement it) and ``depends_on`` is enforced at class-definition
    time. Reactive components are stamped with ``data-pjx-*`` on render and are the
    units the dependency walk (``oob_swaps``) reloads and swaps.
    """

    # State keys this component derives from; the dependency walk swaps a region
    # when its depends_on intersects the route's dirtied keys.
    depends_on: ClassVar[set[str]] = set()

    @classmethod
    @abstractmethod
    def load(cls) -> "ReactiveComponent":
        """Rebuild this component from the current world (zero-arg, type-singleton in v1)."""
        ...

    def state_hash(self) -> str:
        """
        Stable content hash of this component's state, used to gate OOB swaps so a
        region whose value did not change is not re-sent. Defaults to a hash of
        ``model_dump_json()``; override for custom hashing.
        """
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()[:16]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._pjx_reactive = True
        cls._pjx_depends_on = frozenset(getattr(cls, "depends_on", None) or ())
        if "load" in cls.__dict__ and not cls._pjx_depends_on:
            raise TypeError(
                f"{cls.__name__} defines load() but declares no depends_on; a "
                f"reactive component must declare both."
            )
        if "load" in cls.__dict__:
            from .cache import install_cached_load

            install_cached_load(cls)


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
        dirtied: The state keys the route mutated (e.g. {"todos"}). These keys are
            also evicted from the process-global load() cache before dependents are
            reloaded.
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
    # The route mutated `dirtied` before calling us, so any cached load() result
    # for those keys is stale — evict before (re)loading dependents.
    invalidate(dirtied)

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
