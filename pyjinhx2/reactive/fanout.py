"""The manifest walk: which mounted regions are candidates for an OOB swap.

Reads the parsed ``X-PJX-Mounted`` entries and this request's dirtied keys, and
answers one ordered list of candidates. Read-only against the instance registry
(ADR 0009 E7): the Load path is its single writer, and nothing here calls
``register_instance``.

Two name spaces meet in this module and are deliberately not merged. A manifest
entry's ``type`` is the **snake_case tag name** ``discovery.get_class()`` is
keyed by; the instance registry is keyed by the class's **PascalCase**
``__name__``, which is what ``register_rendered_instance`` writes under. The one
conversion between them happens in ``_resolve_registry_entry`` and nowhere else.
The load cache's ``(component_class, load_key)`` space (E13) is a third space
that never crosses either of those.

TODO(#446 owner): nothing server-side stamps ``data-pjx-type`` or
``data-pjx-load`` — ``reactive/root_attrs.py`` stamps only ``data-pjx-id`` and
``data-pjx-hash`` — so a real client-built manifest carries empty ``type``/
``load`` fields today and this walk filters everything out. Patching that
touches L3.4 (#445), which this subtask does not own.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from pyjinhx2 import discovery
from pyjinhx2.reactive.component import ReactiveComponent
from pyjinhx2.reactive.keys import coerce_load_key_str


@dataclass(frozen=True)
class FanoutCandidate:
    """One manifest entry that survived the filters, and how it resolved."""

    type_name: str
    """The entry's snake_case tag name, as the client reported it."""

    component_class: type[ReactiveComponent]
    """The class ``discovery.get_class(type_name)`` answered."""

    instance_id: str
    """The entry's ``data-pjx-id``."""

    load: object
    """The entry's raw ``load`` arg, before any key coercion."""

    status: str
    """``"clean"``, ``"dirty"`` or ``"missing"``."""

    entry: dict[str, Any]
    """The raw manifest entry, so #467 can hash-gate without re-parsing."""

    resolved: object = None
    """Whatever ``registry.resolve()`` returned, or None for a miss."""

    level: object = None
    """The freshly built RenderedLevel on the dirty path, else None."""

    instance: ReactiveComponent | None = None
    """The instance built on the dirty path, else None."""


def _candidate_class(entry: dict[str, Any], dirtied_keys: set[str]) -> type[ReactiveComponent] | None:
    """The reactive class this entry names, when it is dirty; else None.

    The two E9 filters, in the cheap-first order: an unknown tag costs one dict
    lookup, and only a known one pays the key intersection.
    """
    cls = discovery.get_class(str(entry.get("type") or ""))
    if cls is None or not issubclass(cls, ReactiveComponent):
        return None
    if not set(cls._pjx_react_keys) & dirtied_keys:
        return None
    return cls


def _load_key(cls: type[ReactiveComponent], load: object) -> str | None:
    """The load-cache key this class would build for this load arg.

    The exact key ``ReactiveComponent``'s memo wrap derives, so a clean/dirty
    answer here and a cache hit inside ``load()`` can never disagree. A class
    with no PjxKey field keys every instance under None, exactly as the wrap
    does.
    """
    if cls._pjx_key_field is None:
        return None
    return coerce_load_key_str(load)


def walk_manifest(
    manifest_entries: Sequence[dict[str, Any]],
    dirtied_keys: Iterable[str],
) -> list[FanoutCandidate]:
    """The candidates this request's dirtied keys make out of a mounted manifest.

    Args:
        manifest_entries: ``MountedManifest.parse()`` output — dicts shaped
            ``{id, type, load, hash}``, where ``type`` is a snake_case tag name.
        dirtied_keys: This request's normalized dirtied reactive keys.

    Returns:
        One FanoutCandidate per surviving, deduped entry, in manifest order.
        An entry naming an unknown tag, or a class no dirtied key touches, is
        dropped silently — it is not this request's concern.
    """
    dirty = set(dirtied_keys)
    seen: set[tuple[str, str | None]] = set()
    candidates: list[FanoutCandidate] = []
    for entry in manifest_entries:
        cls = _candidate_class(entry, dirty)
        if cls is None:
            continue
        # E10: dedup before any resolve/load/render runs, so two mounted
        # regions standing for the same (class, load arg) cost one of each.
        dedup_key = (str(entry["type"]), _load_key(cls, entry.get("load")))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        candidates.append(
            FanoutCandidate(
                type_name=str(entry["type"]),
                component_class=cls,
                instance_id=str(entry.get("id") or ""),
                load=entry.get("load"),
                status="dirty",
                entry=entry,
            )
        )
    return candidates
