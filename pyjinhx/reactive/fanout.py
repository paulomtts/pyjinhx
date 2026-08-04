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

from markupsafe import Markup

from pyjinhx import discovery, registry
from pyjinhx.reactive.cache import cache_get, cache_has
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.reactive.keys import coerce_load_key_str
from pyjinhx.rendering import render_level
from pyjinhx.root_attrs import stamp_root_attrs
from pyjinhx.segments import ChildRef, RenderedLevel, serialize
from pyjinhx.session import RenderSession, current_session


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

    ``oob_swaps()`` stamps this onto the swapped region's ``data-pjx-hash``
    (``stamp_reactive_root_attrs`` is not wired onto the dirty path's session,
    so nothing else does it first), so the next manifest reports the hash the
    client is actually showing.
    """


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


def _matches_dirtied(
    cls: type[ReactiveComponent], load_key: str | None, dirtied_keys: set[str]
) -> bool:
    """Whether any dirtied key names this class, or this exact instance of it.

    Two shapes reach here. A plain static key (``"todos"``) names every mounted
    instance of a class that declares it. A dynamic key (``reactive_key(TODOS,
    "2")`` -> ``"todos:2"``) names one instance: the mounted region whose own
    load key is ``"2"``. Narrowing lives here rather than in the caller so the
    two shapes are decided in one place and a class with no PjxKey field —
    whose load key is None — simply never matches a dynamic key.
    """
    static = set(cls._pjx_react_keys)
    if static & dirtied_keys:
        return True
    if load_key is None:
        return False
    return bool({f"{key}:{load_key}" for key in static} & dirtied_keys)


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
    if not _matches_dirtied(cls, _load_key(cls, entry.get("load")), dirtied_keys):
        return None
    return cls


def _resolve_registry_entry(
    cls: type[ReactiveComponent], instance_id: str
) -> tuple[object, bool]:
    """This id's registry entry, and whether it resolved at all.

    The one place the snake_case tag name is traded for the PascalCase class
    name the registry is keyed by. A LookupError is caught rather than allowed
    out: the registry is request-scoped (ADR 0009 E6) and written only by this
    request's own renders (E7), so a region outside the primary tree misses
    here as a matter of course. A miss is therefore "nothing cheap to hand
    back", never "this region is gone" — deciding *that* is ``_build_dirty``'s
    failed load, below.
    """
    try:
        return registry.resolve(cls.__name__, instance_id), True
    except LookupError:
        return None, False


def _build_dirty(
    cls: type[ReactiveComponent], instance_id: str, load: object, session: RenderSession
) -> tuple[ReactiveComponent, object]:
    """Re-run this candidate's load and render, and hand back both.

    ``cls.load()`` goes through the L3.2 memo wrap, which is what writes the
    fresh entry to the cache — fanout never calls ``cache_put`` itself, so the
    key derivation stays in exactly one place. ``render_level()`` rather than
    ``render()``: ``oob_swaps()`` splices at a root_span, and only the level
    carries one. The id is stamped after: it identifies the mounted region, not
    the loaded data, so it is never a load() parameter.

    Raises:
        LookupError: ``load()`` cannot build this region any more — the one
            honest signal that a region the client still shows is gone
            server-side. ``walk_manifest`` turns it into a "missing" candidate.
    """
    key_args: dict[str, Any] = {}
    if cls._pjx_key_field is not None:
        key_args[cls._pjx_key_field] = load
    instance = cls.load(**key_args)
    instance.id = instance_id
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
    through rendering.py's single top-level serialize join at step 4, so what
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

    Two passes, not a pairwise scan. The first unions every candidate's tree
    into one id set and one object-identity set; the second keeps a candidate
    unless it appears in either. No `other is not candidate` guard is needed:
    `_contained` reports strict descendants only, so a level contributes
    neither its own root id nor its own object identity to the union and a
    candidate can never match itself.

    A drop needs positive proof — this candidate's id or level object sitting
    inside some tree. A candidate whose only structural data is a live
    instance, and a container side with no tree at all, both simply fail to
    produce that proof and the candidate survives; absence of a check is never
    a drop. Order is preserved and nothing is duplicated.
    """
    if len(candidates) < 2:
        return candidates
    all_ids: set[str] = set()
    all_objects: set[int] = set()
    for other in candidates:
        level = _level_of(other)
        if level is None:
            continue
        ids, objects = _contained(level)
        all_ids |= ids
        all_objects |= objects
    surviving: list[FanoutCandidate] = []
    for candidate in candidates:
        own_level = _level_of(candidate)
        nested = candidate.instance_id in all_ids or (
            own_level is not None and id(own_level) in all_objects
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
        A dirtied key of the form ``"todos:2"`` (``reactive_key()``) narrows to
        the one entry whose own load key is ``"2"``; the bare ``"todos"`` still
        matches every mounted instance of the class.

    Turning a ``"missing"`` candidate into a delete swap is ``delete_swap()``
    below; assembling those fragments with the real swaps into one response
    body is ``oob_swaps()``, and is deliberately not done here.
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
        resolved, _found = _resolve_registry_entry(cls, instance_id)
        if cache_has(cls, dedup_key[1]):
            # E13: the clean answer comes from the load cache's own key space,
            # never from the registry key that resolved above. The registry is
            # consulted only for what it can cheaply hand back, never as the
            # clean/dirty gate — see _resolve_registry_entry on why a miss
            # here is the norm rather than a signal.
            status, instance, level, fresh_hash = "clean", None, None, None
            resolved = (
                resolved if resolved is not None else cache_get(cls, dedup_key[1])
            )
        else:
            # A bare `RenderSession()` installs an AbsolutePathLoader, losing
            # any template roots the caller's real session was configured with.
            # Fall back to the active request_scope()'s session before ever
            # constructing a fresh one, so a caller inside a request never has
            # its dirty-path render silently point at the wrong template dir.
            render_session = session or current_session() or RenderSession()
            try:
                instance, level = _build_dirty(cls, instance_id, load, render_session)
            except LookupError:
                # E17: a key that no longer resolves must not yield a stale
                # instance or render. A failed load is the only thing that
                # actually proves the region is gone, so it — not a registry
                # miss — is what becomes a delete swap.
                status, instance, level, fresh_hash, resolved = (
                    "missing",
                    None,
                    None,
                    None,
                    None,
                )
            else:
                fresh_hash = instance.state_hash()
                if _hash_gate_drops(fresh_hash, entry):
                    # The dedup slot above is deliberately kept: a later
                    # duplicate of this (type, load-key) pair would gate out
                    # identically, so dropping here must not buy it a second
                    # load/render.
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


def _css_attr_value(value: str) -> str:
    """Escape a string for use inside a single-quoted CSS attribute selector.

    Backslash first, then quote: escaping the quote first would leave the
    backslash pass turning its own escape into a literal backslash and letting
    the quote out of the selector.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def delete_swap(candidate: FanoutCandidate) -> Markup:
    """The OOB fragment that removes a gone region from the client's DOM.

    A region whose instance the registry no longer knows about cannot be
    re-rendered — there is nothing left to render. htmx's ``delete`` swap takes
    the element out instead, so the client stops reporting it in the next
    manifest and the pair converges.

    The id is the one the *client* reported, verbatim from the manifest: the
    server has no record of this instance, so there is nothing to re-derive it
    from, and a lookup would only fail again.

    Args:
        candidate: A ``"missing"`` candidate from ``walk_manifest``.

    Returns:
        ``<div hx-swap-oob="delete:[data-pjx-id='ID']"></div>`` — content-free,
        because the swap is the whole instruction.

    Raises:
        ValueError: The candidate is not ``"missing"``. Rendering real content
            for a clean or dirty candidate belongs to ``oob_swaps()``;
            answering an empty string here would hide that caller bug.
    """
    if candidate.status != "missing":
        raise ValueError(
            f"delete_swap expects a 'missing' candidate, got {candidate.status!r}"
        )
    selector = f"delete:[data-pjx-id='{_css_attr_value(candidate.instance_id)}']"
    return Markup(f'<div hx-swap-oob="{selector}"></div>')


def oob_swaps(candidates: list[FanoutCandidate]) -> Markup:
    """The whole OOB response body for one walk's candidates, in candidate order.

    Each dirty candidate's already-built level is stamped with its own
    ``outerHTML`` swap and its ``data-pjx-hash`` at the root_span the original
    parse recorded, in one ``stamp_root_attrs`` splice — never a re-parse of
    rendered markup. ``stamp_reactive_root_attrs`` (the ``on_rendered``
    subscriber that stamps ``data-pjx-hash`` on a normal render) is not wired
    onto the session ``_build_dirty`` uses, so this function stamps the hash
    itself from ``candidate.fresh_hash`` rather than assuming it's already
    there.

    Only two swap values ever leave this function, ``outerHTML:`` here and
    ``delete:`` from ``delete_swap`` (ADR 0001). A clean candidate emits
    nothing: its region is byte-identical to what the client already shows.

    Args:
        candidates: ``walk_manifest()`` output. Every filter — hash gate, dedup,
            nesting, primary-region exclusion — has already been applied; this
            function re-decides none of them.

    Returns:
        The surviving fragments joined by newlines, or ``Markup("")`` when no
        candidate is dirty or missing.
    """
    fragments: list[str] = []
    for candidate in candidates:
        if candidate.status == "dirty":
            level = candidate.level
            # walk_manifest never produces a dirty candidate without a level
            # and a fresh_hash; failing here surfaces that contract break
            # instead of quietly shipping a response that is missing one
            # region's swap or its hash.
            assert isinstance(level, RenderedLevel), (
                f"dirty candidate {candidate.instance_id!r} carries "
                f"{type(level).__name__}, not a RenderedLevel"
            )
            assert candidate.fresh_hash is not None, (
                f"dirty candidate {candidate.instance_id!r} carries no fresh_hash"
            )
            selector = (
                f"outerHTML:[data-pjx-id='{_css_attr_value(candidate.instance_id)}']"
            )
            attrs = {"hx-swap-oob": selector, "data-pjx-hash": candidate.fresh_hash}
            fragments.append(serialize(stamp_root_attrs(level, attrs)))
        elif candidate.status == "missing":
            fragments.append(delete_swap(candidate))
    return Markup("\n".join(fragments))


# TODO(#449): registry.register_rendered_instance is exported but subscribed by
# no production code, so a dirty candidate's fresh RenderedLevel is not visible
# to a later resolve(). Wiring it belongs to whoever owns the re-render/Load
# path, not to this read-only consumer (E7).
