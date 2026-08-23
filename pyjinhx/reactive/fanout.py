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

``reactive/root_attrs.py`` stamps all four fields a manifest entry needs —
``data-pjx-id``, ``data-pjx-type``, ``data-pjx-hash``, and ``data-pjx-load``
for a keyed class — so an entry the client builds arrives here populated. The
entry's ``load`` arrives as the string an HTML attribute round-trips it
through; ``_build_dirty`` validates it back to the key field's declared type
before calling ``load()``.
"""

import re
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, replace
from typing import Any

from markupsafe import Markup

from pyjinhx import discovery, registry
from pyjinhx.reactive.cache import cache_get, cache_has
from pyjinhx.reactive.component import ReactiveComponent, coerce_load_arg
from pyjinhx.reactive.keys import coerce_load_key_str
from pyjinhx.reactive.load_cost import is_too_cheap_to_thread, note_load_cost
from pyjinhx.reactive.root_attrs import record_nested_react_keys
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

    nested_roots: "dict[str, _NestedRoot] | None" = None
    """This candidate's own tree, pre-walked by ``_drop_nested`` — reused by
    ``oob_swaps()``'s ``_preserve_nested`` instead of re-walked from scratch.

    ``_drop_nested`` already calls ``_contained()`` over every surviving
    candidate's level to decide containment; its third return value used to be
    discarded there and recomputed by ``_preserve_nested`` moments later in the
    same request — the same tree walked twice per dirty candidate, every
    request, confirmed by benchmark (#1028). None means "not computed by
    ``_drop_nested``", either because this candidate carries no level or
    because a caller built candidates directly without going through
    ``walk_manifest``; ``_preserve_nested`` falls back to a live walk in
    that case, so behavior for such a caller is unchanged.
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


def _keys_match_dirtied(
    react_keys: tuple[str, ...], load_key: str | None, dirtied_keys: set[str]
) -> bool:
    """Whether any dirtied key names these react keys, or this exact instance.

    Two shapes reach here. A plain static key (``"todos"``) names every mounted
    instance of a class that declares it. A dynamic key (``reactive_key(TODOS,
    "2")`` -> ``"todos:2"``) names one instance: the mounted region whose own
    load key is ``"2"``. Narrowing lives here rather than in the callers so the
    two shapes are decided in one place, and an instance with no load key — an
    unkeyed class — simply never matches a dynamic key.
    """
    static = set(react_keys)
    if static & dirtied_keys:
        return True
    if load_key is None:
        return False
    return bool({f"{key}:{load_key}" for key in static} & dirtied_keys)


def _matches_dirtied(
    cls: type[ReactiveComponent], load_key: str | None, dirtied_keys: set[str]
) -> bool:
    """Whether any dirtied key names this class, or this exact instance of it."""
    return _keys_match_dirtied(cls._pjx_react_keys, load_key, dirtied_keys)


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

    The load is timed around the call that already happens — never a second,
    synthetic one — so the verdict prices the author's real work. Recording it
    here only writes the decision; what reads it is the build pass's choice of
    threading, which lands separately.
    """
    key_args: dict[str, Any] = {}
    if cls._pjx_key_field is not None:
        # The manifest's load arg came off a `data-pjx-load` attribute, so a
        # key declared `int` arrives as `"1"`; restore the declared type before
        # calling the author's load(), whose signature is written against it.
        key_args[cls._pjx_key_field] = coerce_load_arg(cls, load)
    started = time.perf_counter()
    instance = cls.load(**key_args)
    note_load_cost(cls, (time.perf_counter() - started) * 1_000_000)
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

RE_ROOT_PJX_TYPE = re.compile(
    r'data-pjx-type\s*=\s*"([^"]*)"|data-pjx-type\s*=\s*\'([^\']*)\''
)

RE_ROOT_PJX_LOAD = re.compile(
    r'data-pjx-load\s*=\s*"([^"]*)"|data-pjx-load\s*=\s*\'([^\']*)\''
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


def _root_tag_text(level: RenderedLevel) -> str | None:
    """This level's root opening tag, sliced at the offsets the parse recorded.

    Never a re-parse and never a scan of the rendered markup: one read of the
    single tag whose span the original parse wrote down. ``root_span`` is an
    absolute offset into the raw source, so it is rebased by the summed length
    of any whitespace-only prologue segments walked past first.
    """
    skipped = 0
    root: object = None
    for segment in level.segments:
        if isinstance(segment, str) and not segment.strip():
            skipped += len(segment)
            continue
        root = segment
        break
    if not isinstance(root, str):
        return None
    start, end = (offset - skipped for offset in level.root_span)
    return root[start:end]


def _tag_attr(tag_text: str, pattern: re.Pattern[str]) -> str | None:
    """One attribute's value out of a root tag, double- or single-quoted."""
    match = pattern.search(tag_text)
    if match is None:
        return None
    return match.group(1) if match.group(1) is not None else match.group(2)


def _root_instance_id(level: RenderedLevel) -> str | None:
    """The ``data-pjx-id`` on this level's root tag, or None if unstamped.

    The exact inverse of ``stamp_root_attrs``. ``_fill_children`` replaces a
    child's ChildRef with its RenderedLevel and the authored ``id`` attr goes
    with it, so the stamped root tag is the only place a nested level's
    instance identity still lives.
    """
    tag_text = _root_tag_text(level)
    if tag_text is None:
        return None
    return _tag_attr(tag_text, RE_ROOT_PJX_ID)


@dataclass(frozen=True)
class _NestedRoot:
    """One reactive root nested inside a candidate's level, and what decides its stamp."""

    level: RenderedLevel
    """The nested level itself, so a stamp can be spliced into that exact object."""

    component_class: type[ReactiveComponent] | None
    """The class its ``data-pjx-type`` names, or None when the tag names none."""

    react_keys: tuple[str, ...] | None
    """What ``record_nested_react_keys`` recorded for this id, or None if nothing did."""

    load_key: str | None
    """This instance's ``data-pjx-load``, or None for an unkeyed class."""


def _nested_root(
    level: RenderedLevel, instance_id: str, session: RenderSession | None
) -> _NestedRoot:
    """Everything the preserve pass needs about one nested root, read once.

    The class comes from the tag's own ``data-pjx-type`` — a RenderedLevel's
    descriptor carries no back-reference to the class that rendered it, and the
    tag is where ``stamp_reactive_root_attrs`` already wrote the snake_case tag
    name ``discovery`` is keyed by. The react keys come from the session map
    ``record_nested_react_keys`` fills, and stay None when nothing recorded this
    id: absence of information is never read as disjointness.
    """
    tag_text = _root_tag_text(level) or ""
    cls = discovery.get_class(_tag_attr(tag_text, RE_ROOT_PJX_TYPE) or "")
    reactive = cls if cls is not None and issubclass(cls, ReactiveComponent) else None
    return _NestedRoot(
        level=level,
        component_class=reactive,
        react_keys=None
        if session is None
        else session.nested_react_keys.get(instance_id),
        load_key=_tag_attr(tag_text, RE_ROOT_PJX_LOAD),
    )


def _contained(
    level: RenderedLevel, session: RenderSession | None = None
) -> tuple[set[str], set[int], dict[str, _NestedRoot]]:
    """Every id, level object, and reactive root nested *strictly inside* this level.

    Two identity channels, because a descendant can be either shape: an
    unfilled ChildRef still carries the authored ``id`` attr, while a filled
    RenderedLevel carries its stamped root id — plus object identity, which
    settles the case where a survivor's own level object is literally the node
    sitting in another survivor's tree.

    The third channel is additive and read by the preserve pass alone: one
    ``_NestedRoot`` per filled nested level, keyed by its stamped id.
    ``_drop_nested`` ignores it. An unfilled ChildRef contributes nothing to it
    — there is no level to stamp and no rendered tag to read.
    """
    ids: set[str] = set()
    objects: set[int] = set()
    nested_roots: dict[str, _NestedRoot] = {}
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
                nested_roots[nested_id] = _nested_root(node, nested_id, session)
            stack.extend(node.segments)
    return ids, objects, nested_roots


def _drop_nested(
    candidates: list[FanoutCandidate], session: RenderSession | None = None
) -> list[FanoutCandidate]:
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

    The union loop below already calls `_contained` once per candidate with a
    level, purely to decide containment, and used to discard its third return
    value — a map of every nested reactive root inside that candidate's own
    tree. `oob_swaps()`'s `_preserve_nested` would then redo that exact walk
    per dirty candidate a moment later in the same request. Keeping the map
    here and attaching it to whichever candidate survives, so
    `_preserve_nested` can reuse it instead, is what #1028 fixes — at zero
    added walks, since the union loop's own walk already ran regardless.

    `session` is threaded through so the reused map already carries real
    `react_keys` (`_nested_root` needs a session to read `nested_react_keys`);
    omitted, both this walk's containment decision and the reused map behave
    exactly as they did before session-awareness existed here.

    The single-candidate short-circuit below deliberately keeps the shape it
    always had — no `_contained` call at all — rather than walking that one
    candidate's tree just to populate a cache nothing may ever read (a lone
    *clean* or *missing* candidate never reaches `_preserve_nested`, so that
    walk would be pure waste); `oob_swaps` falls back to a live walk for it,
    exactly as it did before this field existed.
    """
    if len(candidates) < 2:
        return candidates
    all_ids: set[str] = set()
    all_objects: set[int] = set()
    nested_roots_by_id: dict[int, dict[str, _NestedRoot]] = {}
    for other in candidates:
        level = _level_of(other)
        if level is None:
            continue
        ids, objects, nested_roots = _contained(level, session)
        all_ids |= ids
        all_objects |= objects
        nested_roots_by_id[id(other)] = nested_roots
    surviving: list[FanoutCandidate] = []
    for candidate in candidates:
        own_level = _level_of(candidate)
        nested = candidate.instance_id in all_ids or (
            own_level is not None and id(own_level) in all_objects
        )
        if not nested:
            cached = nested_roots_by_id.get(id(candidate))
            if cached is not None:
                candidate = replace(candidate, nested_roots=cached)
            surviving.append(candidate)
    return surviving


@dataclass(frozen=True)
class _WorkItem:
    """One manifest entry that survived the filter pass, and where it came from."""

    index: int
    """The entry's position in the manifest, so the reduce pass can restore order."""

    entry: dict[str, Any]
    """The raw manifest entry, carried through for the hash gate."""

    component_class: type[ReactiveComponent]
    """The class ``discovery.get_class()`` answered for this entry's tag."""

    load_key: str | None
    """The load-cache key half of this item's dedup key."""

    instance_id: str
    """The entry's ``data-pjx-id``."""

    load: object
    """The entry's raw ``load`` arg, before any key coercion."""

    resolved: object
    """Whatever the registry (or, on the clean path, the load cache) handed back."""

    clean: bool
    """Whether the load cache already answers this item, so no build is owed."""


def _filter_pass(
    manifest_entries: Sequence[dict[str, Any]],
    dirty: set[str],
    excluded: set[str],
) -> list[_WorkItem]:
    """The surviving, deduped work items, in manifest order.

    Every cheap check lives here and runs to completion before any build
    starts: the dedup ``seen`` set is only a guarantee that one ``(type, load
    key)`` pair costs one load if no build can begin while the set is still
    being filled.
    """
    seen: set[tuple[str, str | None]] = set()
    items: list[_WorkItem] = []
    for index, entry in enumerate(manifest_entries):
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
        load_key = _load_key(cls, entry.get("load"))
        dedup_key = (str(entry["type"]), load_key)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        instance_id = str(entry.get("id") or "")
        resolved, _found = _resolve_registry_entry(cls, instance_id)
        clean = cache_has(cls, load_key)
        if clean and resolved is None:
            # E13: the clean answer comes from the load cache's own key space,
            # never from the registry key that resolved above. The registry is
            # consulted only for what it can cheaply hand back, never as the
            # clean/dirty gate — see _resolve_registry_entry on why a miss
            # here is the norm rather than a signal.
            resolved = cache_get(cls, load_key)
        items.append(
            _WorkItem(
                index=index,
                entry=entry,
                component_class=cls,
                load_key=load_key,
                instance_id=instance_id,
                load=entry.get("load"),
                resolved=resolved,
                clean=clean,
            )
        )
    return items


@dataclass(frozen=True)
class _BuildResult:
    """What one work item's build produced, or the fact that it proved absent."""

    instance: ReactiveComponent | None
    """The freshly loaded instance, or None when the load proved the region gone."""

    level: object
    """The freshly rendered level, or None on the missing path."""

    missing: bool
    """Whether ``load()`` raised LookupError — ADR 0013's proof of absence."""


def _build_one(item: _WorkItem, session: RenderSession) -> _BuildResult:
    """One work item's load and render, with its own absence proof caught.

    The LookupError is caught per item rather than per pass so one region the
    server no longer knows about cannot decide any sibling's outcome. Every
    other exception is left to travel, exactly as it did before the build ran
    off-thread.
    """
    try:
        instance, level = _build_dirty(
            item.component_class, item.instance_id, item.load, session
        )
    except LookupError:
        return _BuildResult(instance=None, level=None, missing=True)
    return _BuildResult(instance=instance, level=level, missing=False)


def _build_pass(
    items: list[_WorkItem], session: RenderSession
) -> dict[int, _BuildResult]:
    """Every non-clean item's build, run on a threadpool, keyed by manifest index.

    ``load()`` is sync, so the concurrency lives here rather than in an async
    variant of the walk — ``walk_manifest`` stays a plain sync callable and
    drives the pool itself. The dict is keyed by index so the reduce pass never
    depends on completion order, and the ``with`` block shuts the pool down
    even when a worker raises.

    The pass is all-or-nothing against anything that is not a LookupError: the
    first ``future.result()`` to re-raise abandons the comprehension, and the
    results its already-finished siblings computed are dropped rather than
    returned. That is deliberate — the reduce pass indexes ``built`` for every
    non-clean item, so a half-filled mapping could only turn a loader's
    exception into a KeyError further downstack, hiding the real cause. A
    region the server genuinely no longer knows about is the one thing that
    must *not* take the pass down with it, and that is exactly what
    ``_build_one`` catches per item.

    A new OS thread starts with a fresh, empty ContextVar context rather than
    inheriting the caller's, so every per-request variable in ``session`` — the
    render session, the load context, the three load-cache dicts — would read
    back as its ``None`` default inside a worker, and a worker's
    ``cache_put()`` would write into a throwaway dict. Copying the caller's
    context and running the build inside it fixes that with no merge-back step:
    a copy holds the *same* dict and set objects ``request_scope()`` built, so
    a worker mutating one in place mutates the request's own.

    One copy per item, not one shared across the pool: a single ``Context``
    cannot be entered by two threads at once, and with more than one worker a
    shared one would raise "cannot enter context: ... is already entered". Each
    copy is taken here, on the submitting thread — taking it inside a worker
    would copy the worker's empty context instead of the request's.

    A pass whose every item is a class already measured as loading faster than a
    thread costs runs inline instead, on the calling thread. Handing such a
    build to the pool spends more on the submit, the context copy and the join
    than the build itself takes. The verdict is read once, before anything is
    built, so a class that earns its verdict partway through this very pass does
    not change where its siblings run — and one unmeasured or costly class is
    enough to keep the whole pass on the pool, since threading is what an
    unproven load() still gets. The inline path takes no context copy: it
    already runs under the request's own ContextVars.
    """
    pending = [item for item in items if not item.clean]
    if not pending:
        return {}
    if all(is_too_cheap_to_thread(item.component_class) for item in pending):
        return {item.index: _build_one(item, session) for item in pending}
    with ThreadPoolExecutor(max_workers=min(8, len(pending))) as pool:
        futures = {
            item.index: pool.submit(copy_context().run, _build_one, item, session)
            for item in pending
        }
        return {index: future.result() for index, future in futures.items()}


def _reduce_pass(
    items: list[_WorkItem],
    built: dict[int, _BuildResult],
    session: RenderSession | None = None,
) -> list[FanoutCandidate]:
    """The surviving candidates, in manifest order, with the late drops applied.

    Walking the work items rather than the results dict is what keeps the
    output in manifest order regardless of which build finished first, and it
    is what ``_drop_nested``'s containment logic depends on.

    ``session`` only reaches ``_drop_nested``, which threads it into the
    containment walk it caches for ``oob_swaps()`` to reuse (#1028); omitted,
    every non-session-dependent behavior here is unchanged.
    """
    candidates: list[FanoutCandidate] = []
    for item in items:
        if item.clean:
            status, instance, level, fresh_hash = "clean", None, None, None
            resolved = item.resolved
        else:
            result = built[item.index]
            if result.missing:
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
                instance, level = result.instance, result.level
                assert instance is not None
                fresh_hash = instance.state_hash()
                if _hash_gate_drops(fresh_hash, item.entry):
                    # The dedup slot the filter pass took is deliberately kept:
                    # a later duplicate of this (type, load-key) pair would gate
                    # out identically, so dropping here must not buy it a second
                    # load/render.
                    continue
                status, resolved = "dirty", item.resolved
        candidates.append(
            FanoutCandidate(
                type_name=str(item.entry["type"]),
                component_class=item.component_class,
                instance_id=item.instance_id,
                load=item.load,
                status=status,
                entry=item.entry,
                resolved=resolved,
                level=level,
                instance=instance,
                fresh_hash=fresh_hash,
            )
        )
    return _drop_nested(candidates, session)


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

    Three passes, not one loop. The filter pass runs every cheap check and
    finishes its dedup before anything is built; the build pass runs the loads
    and renders on a threadpool, since ``load()`` is sync and this walk stays a
    plain sync call; the reduce pass hash-gates, maps a failed load to
    "missing", and reassembles by manifest position.
    """
    items = _filter_pass(
        manifest_entries, set(dirtied_keys), _mounted_ids_in(primary_html)
    )
    # A bare `RenderSession()` installs an AbsolutePathLoader, losing any
    # template roots the caller's real session was configured with. Fall back
    # to the active request_scope()'s session before ever constructing a fresh
    # one, so a caller inside a request never has its dirty-path render
    # silently point at the wrong template dir.
    render_session = session or current_session() or RenderSession()
    # Subscribed here rather than inside _build_dirty: one append per walk
    # covers every build the pass runs, and the guard mirrors the one
    # responses.py:74 uses for accumulate_assets, so a session that already
    # carries the recorder — a second walk, or a caller that wired it — never
    # records the same render twice.
    if record_nested_react_keys not in render_session.on_rendered:
        render_session.on_rendered.append(record_nested_react_keys)
    return _reduce_pass(items, _build_pass(items, render_session), render_session)


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


def _preserve_nested(
    level: RenderedLevel,
    dirtied_keys: set[str],
    candidate_ids: set[str],
    session: RenderSession | None,
    nested_roots: "dict[str, _NestedRoot] | None" = None,
) -> None:
    """Splice ``hx-preserve="true"`` onto each nested root this swap must not disturb.

    A nested reactive region whose keys this request never dirtied is not the
    parent's to replace: htmx keeps the live element when the incoming markup
    carries ``hx-preserve``, so the parent's swap lands around it instead of
    through it. Stamping is deliberately conservative — a nested root is stamped
    only on positive proof of disjointness, so an unresolvable class or an
    unrecorded id simply keeps today's behavior.

    ``hx-preserve`` is a documented no-op for an id the client does not already
    show, so a first-mount nested region needs no special case here.

    htmx resolves the live element by the incoming tag's plain ``id`` attribute
    (``handlePreservedElements`` -> ``getElementById``), not by ``data-pjx-id``,
    so retention only actually lands for a region whose own template root
    carries a stable authored ``id``. Stamping one here would not help: the
    element already on the page came from a render that carried none either.

    Runs after the candidate's own root stamp, never before: the shape where the
    "nested" root *is* the fragment's own swap target (a parent whose whole
    template is one reactive child) is exactly the shape ``stamp_root_attrs``
    already refuses with RootStampCollisionError, so no fragment reaches this
    pass with its own swap target among the nested roots.

    ``nested_roots``, when given, is ``_drop_nested``'s own walk of this exact
    level, reused instead of re-derived (#1028: the two walks found the same
    thing every time, since nothing mutates a level's *structure* between the
    build pass and this call — only its root tag's attrs, which `_contained`
    never reads). ``None`` means no caller supplied one — a candidate built
    outside ``walk_manifest``, say — so a live walk runs exactly as it always
    did.
    """
    if nested_roots is None:
        _ids, _objects, nested_roots = _contained(level, session)
    for nested_id, nested in nested_roots.items():
        if nested_id in candidate_ids:
            continue
        cls = nested.component_class
        if cls is None or not cls.retain_across_parent_swaps:
            continue
        if nested.react_keys is None:
            continue
        if _keys_match_dirtied(nested.react_keys, nested.load_key, dirtied_keys):
            continue
        stamp_root_attrs(nested.level, {"hx-preserve": "true"}, nested=True)


def oob_swaps(
    candidates: list[FanoutCandidate],
    dirtied_keys: Iterable[str] = (),
    session: RenderSession | None = None,
) -> Markup:
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
        dirtied_keys: This request's normalized dirtied reactive keys, so a
            nested region none of them names can be preserved across its
            parent's swap. Empty by default: a caller that supplies none gets
            today's behavior, which stamps nothing.
        session: The session carrying ``nested_react_keys``; defaults to the
            active ``request_scope()``'s, and to None outside one, in which
            case nothing is stamped.

    Returns:
        The surviving fragments joined by newlines, or ``Markup("")`` when no
        candidate is dirty or missing.
    """
    dirtied = set(dirtied_keys)
    render_session = session or current_session()
    candidate_ids = {
        candidate.instance_id
        for candidate in candidates
        if candidate.status in ("dirty", "missing")
    }
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
            stamp_root_attrs(level, attrs)
            _preserve_nested(
                level, dirtied, candidate_ids, render_session, candidate.nested_roots
            )
            fragments.append(serialize(level))
        elif candidate.status == "missing":
            fragments.append(delete_swap(candidate))
    return Markup("\n".join(fragments))


# TODO(#449): registry.register_rendered_instance is exported but subscribed by
# no production code, so a dirty candidate's fresh RenderedLevel is not visible
# to a later resolve(). Wiring it belongs to whoever owns the re-render/Load
# path, not to this read-only consumer (E7).
