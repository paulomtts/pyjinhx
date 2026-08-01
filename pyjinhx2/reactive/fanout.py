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

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from pyjinhx2 import discovery, registry
from pyjinhx2.reactive.cache import cache_get, cache_has
from pyjinhx2.reactive.component import ReactiveComponent
from pyjinhx2.reactive.keys import coerce_load_key_str
from pyjinhx2.render import render_level
from pyjinhx2.segments import ChildRef, RenderedLevel
from pyjinhx2.session import RenderSession, current_session


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

    fresh_hash: str | None = None
    """The dirty path's freshly computed state hash; None on clean/missing.

    #471 stamps this back onto the swapped region's ``data-pjx-hash``, so the
    next manifest reports the hash the client is actually showing.
    """


def _candidate_class(
    entry: dict[str, Any], dirtied_keys: set[str]
) -> type[ReactiveComponent] | None:
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


def _resolve_registry_entry(
    cls: type[ReactiveComponent], instance_id: str
) -> tuple[object, bool]:
    """This id's registry entry, and whether it resolved at all.

    The one place the snake_case tag name is traded for the PascalCase class
    name the registry is keyed by. A LookupError is caught rather than allowed
    out: one region the client still shows but the server no longer knows about
    must not take the whole walk down — it becomes a "missing" candidate, which
    is #470's hook point for a delete swap.
    """
    try:
        return registry.resolve(cls.__name__, instance_id), True
    except LookupError:
        return None, False


def _build_dirty(
    cls: type[ReactiveComponent], instance_id: str, load: object, session: RenderSession
) -> tuple[ReactiveComponent, object]:
    """Re-run this candidate's load and render, and hand back both.

    ``instance.load()`` goes through the L3.2 memo wrap, which is what writes
    the fresh entry to the cache — fanout never calls ``cache_put`` itself, so
    the key derivation stays in exactly one place. ``render_level()`` rather
    than ``render()``: #471 splices at a root_span, and only the level carries
    one.
    """
    fields: dict[str, Any] = {"id": instance_id}
    if cls._pjx_key_field is not None:
        fields[cls._pjx_key_field] = load
    instance = cls(**fields)
    instance.load()
    return instance, render_level(instance, session)


def _hash_gate_drops(fresh_hash: str, entry: dict[str, Any]) -> bool:
    """Whether this re-rendered instance is byte-identical to what the client shows.

    A dirtied key only says the *data* may have moved, never that the *output*
    did. When the fresh state hash equals the one the client reported for this
    region, the swap would replace the region with itself, so it is dropped.
    A manifest entry with no ``hash`` at all can never match a real digest and
    therefore always survives — an unstamped region is refreshed, not skipped.
    """
    return fresh_hash == entry.get("hash")


RE_ROOT_PJX_ID = re.compile(
    r'data-pjx-id\s*=\s*"([^"]*)"|data-pjx-id\s*=\s*\'([^\']*)\''
)


def _mounted_ids_in(primary_html: object) -> set[str]:
    """Every ``data-pjx-id`` the primary response's markup already carries.

    A string scan rather than a segment-tree walk, unlike ``_drop_nested``: by
    the time fan-out runs (T2 step 5) the primary render has already been
    through render.py's single top-level serialize join at step 4, so what
    reaches here is a serialized str/Markup with no tree left to walk. Markup
    and str are read identically — the regex sees ``str(primary_html)`` either
    way. Best-effort by design: a truncated or malformed fragment simply yields
    the ids the regex can still see.
    """
    if not primary_html:
        return set()
    return {
        double or single
        for double, single in RE_ROOT_PJX_ID.findall(str(primary_html))
        if double or single
    }


def _level_of(candidate: FanoutCandidate) -> RenderedLevel | None:
    """The candidate's own segment tree, from either field, or None.

    A dirty candidate carries a fresh ``level``; a clean one carries only
    whatever ``registry.resolve()`` handed back, which is a RenderedLevel for a
    cached region and a live instance otherwise. A live instance has no tree, so
    it answers None — a side with no tree is never walked and never guessed at.
    """
    if isinstance(candidate.level, RenderedLevel):
        return candidate.level
    if isinstance(candidate.resolved, RenderedLevel):
        return candidate.resolved
    return None


def _root_instance_id(level: RenderedLevel) -> str | None:
    """The ``data-pjx-id`` on this level's root tag, or None if unstamped.

    The exact inverse of ``stamp_root_attrs``: one read of the single tag whose
    offsets the original parse recorded, never a re-parse and never a scan of
    the rendered markup. ``_fill_children`` replaces a child's ChildRef with its
    RenderedLevel and the authored ``id`` attr goes with it, so the stamped root
    tag is the only place a nested level's instance identity still lives.
    """
    root = level.segments[0] if level.segments else ""
    if not isinstance(root, str):
        return None
    start, end = level.root_span
    match = RE_ROOT_PJX_ID.search(root[start:end])
    if match is None:
        return None
    return match.group(1) if match.group(1) is not None else match.group(2)


def _contained(level: RenderedLevel) -> tuple[set[str], set[int]]:
    """Every id and every level object nested *strictly inside* this level.

    Two identity channels, because a descendant can be either shape: an
    unfilled ChildRef still carries the authored ``id`` attr, while a filled
    RenderedLevel carries its stamped root id — plus object identity, which
    settles the case where a survivor's own level object is literally the node
    sitting in another survivor's tree.
    """
    ids: set[str] = set()
    objects: set[int] = set()
    stack: list[object] = list(level.segments)
    while stack:
        node = stack.pop()
        if isinstance(node, ChildRef):
            nested_id = node.attrs.get("id")
            if nested_id:
                ids.add(nested_id)
        elif isinstance(node, RenderedLevel):
            objects.add(id(node))
            nested_id = _root_instance_id(node)
            if nested_id:
                ids.add(nested_id)
            stack.extend(node.segments)
    return ids, objects


def _drop_nested(candidates: list[FanoutCandidate]) -> list[FanoutCandidate]:
    """Drop every candidate whose region sits inside another survivor's region.

    The v0.x behavior (a parent's swap already carries its children, so a child
    swap is redundant and would fight the parent's) reached through the segment
    tree instead of a substring search over rendered HTML: the tree already
    records containment, so nothing here re-parses or re-serializes markup.

    A drop needs positive proof — a concrete containing RenderedLevel on some
    *other* survivor whose tree holds this candidate's id or level object. A
    candidate whose only structural data is a live instance, and a container
    side with no tree at all, both simply fail to produce that proof and the
    candidate survives; absence of a check is never a drop. Order is preserved
    and nothing is duplicated.
    """
    if len(candidates) < 2:
        return candidates
    trees = {
        id(other): _contained(level)
        for other in candidates
        if (level := _level_of(other)) is not None
    }
    surviving: list[FanoutCandidate] = []
    for candidate in candidates:
        own_level = _level_of(candidate)
        nested = any(
            candidate.instance_id in ids
            or (own_level is not None and id(own_level) in objects)
            for other in candidates
            if other is not candidate
            for ids, objects in (trees.get(id(other), (frozenset(), frozenset())),)
        )
        if not nested:
            surviving.append(candidate)
    return surviving


def walk_manifest(
    manifest_entries: Sequence[dict[str, Any]],
    dirtied_keys: Iterable[str],
    session: RenderSession | None = None,
    primary_html: object = None,
) -> list[FanoutCandidate]:
    """The candidates this request's dirtied keys make out of a mounted manifest.

    Args:
        manifest_entries: ``MountedManifest.parse()`` output — dicts shaped
            ``{id, type, load, hash}``, where ``type`` is a snake_case tag name.
        dirtied_keys: This request's normalized dirtied reactive keys.
        session: the RenderSession a dirty candidate's re-render runs against;
            a fresh one is built per call when omitted.
        primary_html: this request's already-serialized primary response, when
            there is one. Every region it already contains is excluded from the
            fan-out — otherwise that region swaps twice, once as primary content
            and once OOB (the T2 ordering fact). Omitted or None means no
            exclusion, so a caller with no primary body is unaffected.

    Returns:
        One FanoutCandidate per surviving, deduped entry, in manifest order.
        An entry naming an unknown tag, or a class no dirtied key touches, is
        dropped silently — it is not this request's concern. A candidate's
        ``status`` is one of ``"clean"``, ``"dirty"``, or ``"missing"``.
        A dirty entry whose freshly rendered state hash equals the hash the
        client reported is dropped too: the region changed keys but not output.
        A candidate whose region is structurally nested inside another
        survivor's region is dropped: the parent's swap already carries it, and
        so is one whose id the primary response already carries.

    Deliberately not done here, each owned by the next subtask in L3.5: turning
    a ``"missing"`` candidate into a delete swap (#470); splicing
    ``hx-swap-oob`` at a level's root_span (#471).
    """
    dirty = set(dirtied_keys)
    excluded = _mounted_ids_in(primary_html)
    seen: set[tuple[str, str | None]] = set()
    candidates: list[FanoutCandidate] = []
    for entry in manifest_entries:
        # Cheapest filter first, ahead of the two E9 ones: one set membership
        # against a string id, before any class lookup, dedup bookkeeping,
        # resolve, load or render is paid for.
        if excluded and str(entry.get("id") or "") in excluded:
            continue
        cls = _candidate_class(entry, dirty)
        if cls is None:
            continue
        # E10: dedup before any resolve/load/render runs, so two mounted
        # regions standing for the same (class, load arg) cost one of each.
        dedup_key = (str(entry["type"]), _load_key(cls, entry.get("load")))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        instance_id = str(entry.get("id") or "")
        load = entry.get("load")
        resolved, found = _resolve_registry_entry(cls, instance_id)
        if not found:
            status, instance, level, fresh_hash = "missing", None, None, None
        elif cache_has(cls, dedup_key[1]):
            # E13: the clean answer comes from the load cache's own key space,
            # never from the registry key that resolved above.
            status, instance, level, fresh_hash = "clean", None, None, None
            resolved = (
                resolved if resolved is not None else cache_get(cls, dedup_key[1])
            )
        else:
            # A bare `RenderSession()` defaults to template_dir="templates" —
            # the wrong templates outside a test with that literal directory.
            # Fall back to the active request_scope()'s session before ever
            # constructing a fresh one, so a caller inside a request never has
            # its dirty-path render silently point at the wrong template dir.
            render_session = session or current_session() or RenderSession()
            instance, level = _build_dirty(cls, instance_id, load, render_session)
            fresh_hash = instance.state_hash()
            if _hash_gate_drops(fresh_hash, entry):
                # The dedup slot above is deliberately kept: a later duplicate
                # of this (type, load-key) pair would gate out identically, so
                # dropping here must not buy it a second load/render.
                continue
            status = "dirty"
        candidates.append(
            FanoutCandidate(
                type_name=str(entry["type"]),
                component_class=cls,
                instance_id=instance_id,
                load=load,
                status=status,
                entry=entry,
                resolved=resolved,
                level=level,
                instance=instance,
                fresh_hash=fresh_hash,
            )
        )
    return _drop_nested(candidates)


# TODO(#449): registry.register_rendered_instance is exported but subscribed by
# no production code, so a dirty candidate's fresh RenderedLevel is not visible
# to a later resolve(). Wiring it belongs to whoever owns the re-render/Load
# path, not to this read-only consumer (E7).
