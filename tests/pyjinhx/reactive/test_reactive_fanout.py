"""Unit tests for the manifest walk: filter, dedup, and clean/dirty resolution."""

import dataclasses
import pathlib
import re
import sys
import threading
import time
from typing import Annotated, cast

import pytest

from pyjinhx import discovery, registry
from pyjinhx._component import BaseComponent
from pyjinhx.reactive import fanout
from pyjinhx.reactive.cache import cache_has, cache_put
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.reactive.fanout import (
    FanoutCandidate,
    _drop_nested,
    _mounted_ids_in,
    delete_swap,
    oob_swaps,
    walk_manifest,
)
from pyjinhx.reactive.load_cost import note_load_cost
from pyjinhx.segments import ChildRef, RenderedLevel
from pyjinhx.session import (
    RenderSession,
    current_session,
    get_cache_store,
    get_load_context,
    request_scope,
)

LOAD_CALLS: list[str] = []

GONE_KEYS: set[str] = set()
"""Load keys `FanoutWidget.load()` refuses to build, standing for a region the
server no longer knows about. A failed load is the only thing that makes a
candidate "missing" — a registry miss does not, because the registry is
request-scoped (ADR 0009 E6) and misses for every out-of-primary region."""


class FanoutWidget(ReactiveComponent, react=("todos",)):
    """A reactive component keyed by ``pjx_key``, whose load() is counted."""

    pjx_key: Annotated[str, PjxKey()] = ""
    data: str = ""

    @classmethod
    def load(cls, pjx_key: str) -> "FanoutWidget":
        LOAD_CALLS.append(pjx_key)
        if pjx_key in GONE_KEYS:
            raise LookupError(f"no widget for {pjx_key!r}")
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")


class QuietWidget(ReactiveComponent, react=("other",)):
    """A reactive component that no test's dirtied keys ever touch."""


class OwnedWidget(ReactiveComponent, react=("other",)):
    """A nested class that declares itself fully owned by its parent's swap."""

    retain_across_parent_swaps = False


class LoudWidget(ReactiveComponent, react=("todos",)):
    """A reactive component that reacts to the same keys as FanoutWidget but is
    never measured, so a pass mixing it with a too-cheap class must still thread."""

    pjx_key: Annotated[str, PjxKey()] = ""
    data: str = ""

    @classmethod
    def load(cls, pjx_key: str) -> "LoudWidget":
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")


class PlainWidget(BaseComponent):
    """A discovery-registered component that is NOT a ReactiveComponent.

    A manifest naming a real tag whose class is non-reactive must be dropped by
    the `issubclass` half of `_candidate_class`, not by the unknown-tag half.
    """


SEEN_SESSIONS: list[object] = []
"""What `current_session()` answered inside each SpyWidget.load() call."""

SEEN_LOAD_CONTEXTS: list[object] = []
"""What `get_load_context()` answered inside each SpyWidget.load() call."""

SEEN_THREADS: set[int] = set()
"""The thread each SpyWidget.load() ran on, to prove more than one was used."""

STAT_CALLS: list[str] = []
"""Template paths the loader's freshness closure actually stat()'ed this walk.

Only stats made from inside `uptodate()` are recorded. `get_source()`'s own
initial mtime read and `Path.is_file()`'s probe go through the same
`Path.stat`, and counting those would measure template *loading* rather than
the per-lookup freshness re-check this test is about.
"""


class SpyWidget(ReactiveComponent, react=("todos",)):
    """A reactive component whose load() records its worker's context view."""

    pjx_key: Annotated[str, PjxKey()] = ""
    data: str = ""

    @classmethod
    def load(cls, pjx_key: str) -> "SpyWidget":
        SEEN_SESSIONS.append(current_session())
        SEEN_LOAD_CONTEXTS.append(get_load_context())
        SEEN_THREADS.add(threading.get_ident())
        if pjx_key == "boom":
            raise ValueError("loader exploded")
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")


@pytest.fixture(autouse=True)
def _clean_registries(tmp_path, monkeypatch):
    """Publish a tag -> class map for the two test classes and reset call spies."""
    LOAD_CALLS.clear()
    GONE_KEYS.clear()
    SEEN_SESSIONS.clear()
    SEEN_LOAD_CONTEXTS.clear()
    SEEN_THREADS.clear()
    STAT_CALLS.clear()
    spy_path = tmp_path / "spy_widget.pjx"
    spy_path.write_text("<div>{{ pjx_key }}</div>")
    fanout_path = tmp_path / "fanout_widget.pjx"
    quiet_path = tmp_path / "quiet_widget.pjx"
    fanout_path.write_text("<div>{{ pjx_key }}</div>")
    quiet_path.write_text("<div>quiet</div>")
    owned_path = tmp_path / "owned_widget.pjx"
    owned_path.write_text("<div>owned</div>")
    plain_path = tmp_path / "plain_widget.pjx"
    plain_path.write_text("<div>plain</div>")
    loud_path = tmp_path / "loud_widget.pjx"
    loud_path.write_text("<div>{{ pjx_key }}</div>")
    discovery.build_registry(
        tmp_path,
        [FanoutWidget, QuietWidget, PlainWidget, SpyWidget, LoudWidget, OwnedWidget],
    )
    # `_resolve_template_path` walks the class's *defining module's* directory
    # (this test file's dir), not `template_dir` passed to `build_registry` —
    # the two are deliberately different concerns (tag lookup vs. file probe).
    # Point each descriptor's `template_path` at this test's tmp_path file, the
    # same way tests/pyjinhx/test_render_integration.py does, so render_level()
    # finds a real file instead of falling back to an ancestor's unprobed guess.
    # The loader is absolute-only, so each descriptor carries the full path.
    PlainWidget.__pjx_descriptor__ = dataclasses.replace(
        PlainWidget.__pjx_descriptor__, template_path=plain_path
    )
    FanoutWidget.__pjx_descriptor__ = dataclasses.replace(
        FanoutWidget.__pjx_descriptor__, template_path=fanout_path
    )
    QuietWidget.__pjx_descriptor__ = dataclasses.replace(
        QuietWidget.__pjx_descriptor__, template_path=quiet_path
    )
    SpyWidget.__pjx_descriptor__ = dataclasses.replace(
        SpyWidget.__pjx_descriptor__, template_path=spy_path
    )
    LoudWidget.__pjx_descriptor__ = dataclasses.replace(
        LoudWidget.__pjx_descriptor__, template_path=loud_path
    )
    OwnedWidget.__pjx_descriptor__ = dataclasses.replace(
        OwnedWidget.__pjx_descriptor__, template_path=owned_path
    )
    yield


def entry(
    type_name: str, instance_id: str, load: object = None, hash_: str = "h"
) -> dict:
    """Build one synthetic X-PJX-Mounted manifest entry."""
    return {"type": type_name, "id": instance_id, "load": load, "hash": hash_}


def scope():
    """`request_scope()`, kept as a named helper so call sites read the same
    whether or not a future test needs to pass it a pre-built session."""
    return request_scope()


def test_unknown_type_is_dropped():
    with scope():
        assert walk_manifest([entry("no_such_widget", "a")], {"todos"}) == []


def test_registered_but_non_reactive_type_is_dropped():
    with scope():
        assert walk_manifest([entry("plain_widget", "a")], {"todos"}) == []
        assert discovery.get_class("plain_widget") is PlainWidget


def test_entry_whose_keys_miss_the_dirtied_set_is_dropped():
    with scope():
        assert walk_manifest([entry("quiet_widget", "a")], {"todos"}) == []


def test_entry_whose_keys_hit_the_dirtied_set_is_kept():
    with scope():
        [candidate] = walk_manifest(
            [entry("fanout_widget", "a", load="todo-1")], {"todos"}
        )
        assert candidate.component_class is FanoutWidget
        assert candidate.instance_id == "a"


def test_empty_manifest_and_empty_dirtied_keys_answer_empty():
    with scope():
        assert walk_manifest([], {"todos"}) == []
        assert walk_manifest([entry("fanout_widget", "a")], set()) == []


def test_duplicate_type_and_load_pairs_collapse_to_one_candidate():
    manifest = [
        entry("fanout_widget", "a", load="todo-1"),
        entry("fanout_widget", "b", load="todo-1"),
        entry("fanout_widget", "c", load="todo-2"),
    ]
    with scope():
        candidates = walk_manifest(manifest, {"todos"})
        assert [c.instance_id for c in candidates] == ["a", "c"]


def test_a_dynamic_key_matches_only_the_instance_whose_load_key_it_names():
    """`dirty(reactive_key(TODOS, "2"))` reloads row 2 and leaves row 1 alone."""
    manifest = [
        entry("fanout_widget", "row-1", load="1"),
        entry("fanout_widget", "row-2", load="2"),
    ]
    with scope():
        registry.register_instance(FanoutWidget.__name__, "row-1", "e1")
        registry.register_instance(FanoutWidget.__name__, "row-2", "e2")
        candidates = walk_manifest(manifest, {"todos:2"})
    assert [c.instance_id for c in candidates] == ["row-2"]
    assert LOAD_CALLS == ["2"]


def test_a_static_key_still_matches_every_instance_of_the_class():
    """The dynamic match narrows; it must not shadow the plain static match."""
    manifest = [
        entry("fanout_widget", "row-1", load="1"),
        entry("fanout_widget", "row-2", load="2"),
    ]
    with scope():
        registry.register_instance(FanoutWidget.__name__, "row-1", "e1")
        registry.register_instance(FanoutWidget.__name__, "row-2", "e2")
        candidates = walk_manifest(manifest, {"todos"})
    assert [c.instance_id for c in candidates] == ["row-1", "row-2"]


def test_a_dynamic_key_naming_an_unmounted_load_matches_nothing():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "row-1", "e1")
        assert (
            walk_manifest([entry("fanout_widget", "row-1", load="1")], {"todos:9"})
            == []
        )
        assert LOAD_CALLS == []


def test_cache_hit_answers_clean_without_calling_load():
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        [candidate] = walk_manifest(
            [entry("fanout_widget", "a", load="todo-1")], {"todos"}
        )
        assert candidate.status == "clean"
        assert candidate.resolved == "resolved-entry"
        assert candidate.level is None
        assert LOAD_CALLS == []


def test_cache_miss_loads_once_renders_and_caches():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        [candidate] = walk_manifest(
            [entry("fanout_widget", "a", load="todo-1")], {"todos"}
        )
        assert candidate.status == "dirty"
        assert LOAD_CALLS == ["todo-1"]
        # The build ran on a pool worker, but the worker ran inside a copy of
        # this request's context, so its memo wrap's cache_put() mutated the
        # store this scope still holds.
        assert cache_has(FanoutWidget, "todo-1") is True
        assert candidate.level is not None
        assert isinstance(candidate.level, RenderedLevel)
        assert candidate.level.root_span is not None
        assert candidate.instance is not None


def test_a_failed_load_is_a_miss_and_does_not_abort_the_walk():
    GONE_KEYS.add("todo-1")
    with scope():
        manifest = [
            entry("fanout_widget", "gone", load="todo-1"),
            entry("fanout_widget", "b", load="todo-2"),
        ]
        gone, alive = walk_manifest(manifest, {"todos"})
        assert gone.status == "missing"
        assert gone.resolved is None
        assert alive.status == "dirty"


def test_an_unregistered_entry_still_rebuilds_rather_than_deleting():
    """The registry is request-scoped and written only by this request's own
    renders (ADR 0009 E6/E7), so every region outside the primary tree misses
    it. A miss must therefore mean "rebuild", never "delete" — otherwise a
    plain fan-out would wipe the regions it exists to refresh."""
    with scope():
        [candidate] = walk_manifest(
            [entry("fanout_widget", "never-registered", load="todo-1")], {"todos"}
        )
        assert candidate.status == "dirty"
        assert candidate.level is not None


def test_the_walk_never_writes_to_the_instance_registry(monkeypatch):
    # Deviation from the plan's literal test: the plan seeds the registry
    # entry *after* patching `register_instance`, so that setup call is
    # itself captured and `assert calls == []` fails regardless of
    # walk_manifest's behavior. Seed first, patch second, so the spy only
    # sees calls walk_manifest itself makes.
    calls: list[tuple] = []
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        monkeypatch.setattr(
            "pyjinhx.reactive.fanout.registry.register_instance",
            lambda *args: calls.append(args),
            raising=False,
        )
        walk_manifest([entry("fanout_widget", "a", load="todo-1")], {"todos"})
        assert calls == []


def fresh_hash_for(load: object) -> str:
    """The state hash `walk_manifest`'s dirty path will compute for this load arg.

    Built from an instance shaped exactly like `_build_dirty` builds one, so a
    test can seed a manifest entry with the *matching* hash without hardcoding
    a digest that changes whenever the model's fields do.
    """
    return FanoutWidget(id="probe", pjx_key=str(load), data=f"data:{load}").state_hash()


def test_dirty_candidate_whose_fresh_hash_matches_the_manifest_hash_is_dropped():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        manifest = [
            entry("fanout_widget", "a", load="todo-1", hash_=fresh_hash_for("todo-1"))
        ]
        assert walk_manifest(manifest, {"todos"}) == []


def test_dirty_candidate_whose_fresh_hash_differs_survives_carrying_that_hash():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        manifest = [entry("fanout_widget", "a", load="todo-1", hash_="stale-hash")]
        [candidate] = walk_manifest(manifest, {"todos"})
        assert candidate.status == "dirty"
        assert candidate.fresh_hash == fresh_hash_for("todo-1")
        assert candidate.fresh_hash != "stale-hash"


def test_dirty_candidate_whose_manifest_entry_has_no_hash_key_survives():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        # A manifest entry that never carried a `hash` field — `entry.get("hash")`
        # answers None, which must read as "unknown", never as "unchanged".
        manifest = [{"type": "fanout_widget", "id": "a", "load": "todo-1"}]
        [candidate] = walk_manifest(manifest, {"todos"})
        assert candidate.status == "dirty"
        assert candidate.fresh_hash == fresh_hash_for("todo-1")


def test_clean_candidate_is_not_hash_gated_and_carries_no_fresh_hash(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        FanoutWidget,
        "state_hash",
        lambda self: calls.append(self.id) or "computed",
        raising=False,
    )
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        # The manifest reports the very hash the patched state_hash() would
        # answer: a clean candidate must survive anyway, because no fresh
        # render exists for the gate to compare against.
        manifest = [entry("fanout_widget", "a", load="todo-1", hash_="computed")]
        [candidate] = walk_manifest(manifest, {"todos"})
        assert candidate.status == "clean"
        assert candidate.fresh_hash is None
        assert calls == []


def test_missing_candidate_is_not_hash_gated_and_carries_no_fresh_hash():
    GONE_KEYS.add("todo-1")
    with scope():
        # load() refuses this key, so the entry is "missing" — #470's
        # delete-swap input, which this gate must not consume even when the
        # reported hash is the matching one.
        manifest = [
            entry(
                "fanout_widget", "gone", load="todo-1", hash_=fresh_hash_for("todo-1")
            )
        ]
        [candidate] = walk_manifest(manifest, {"todos"})
        assert candidate.status == "missing"
        assert candidate.fresh_hash is None


def test_mixed_manifest_gates_only_the_dirty_entries():
    GONE_KEYS.add("todo-4")
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        manifest = [
            # clean: cached, reports the hash its own fresh render would have
            entry("fanout_widget", "a", load="todo-1", hash_=fresh_hash_for("todo-1")),
            # dirty + gated out: fresh hash equals the reported one
            entry(
                "fanout_widget", "same", load="todo-2", hash_=fresh_hash_for("todo-2")
            ),
            # dirty + survives: reported hash is stale
            entry("fanout_widget", "moved", load="todo-3", hash_="stale"),
            # missing: load() refuses it, gate must not touch it
            entry(
                "fanout_widget", "gone", load="todo-4", hash_=fresh_hash_for("todo-4")
            ),
        ]
        candidates = walk_manifest(manifest, {"todos"})
        assert [(c.instance_id, c.status) for c in candidates] == [
            ("a", "clean"),
            ("moved", "dirty"),
            ("gone", "missing"),
        ]
        assert [c.fresh_hash for c in candidates] == [
            None,
            fresh_hash_for("todo-3"),
            None,
        ]
        # The gated-out entry still ran its load — the gate decides *after* the
        # re-render, which is the whole point: it compares fresh output, not
        # a guess about the data. The "gone" entry loads too — its refusal is
        # what establishes it is missing — so all three appear here. Sorted:
        # the build pass runs the loads on a threadpool, so which one records
        # itself first is not fixed.
        assert sorted(LOAD_CALLS) == ["todo-2", "todo-3", "todo-4"]


def test_mixed_manifest_produces_the_expected_ordered_candidate_list():
    GONE_KEYS.add("todo-3")
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        manifest = [
            entry("no_such_widget", "x"),
            entry("quiet_widget", "y"),
            entry("fanout_widget", "a", load="todo-1"),
            entry("fanout_widget", "dup", load="todo-1"),
            entry("fanout_widget", "c", load="todo-2"),
            entry("fanout_widget", "gone", load="todo-3"),
        ]
        candidates = walk_manifest(manifest, {"todos"})
        assert [(c.instance_id, c.status) for c in candidates] == [
            ("a", "clean"),
            ("c", "dirty"),
            ("gone", "missing"),
        ]
        # The clean candidate was never loaded; the missing one paid the one
        # failed load that established it is gone. Sorted: the two loads race
        # each other on the build pass threadpool.
        assert sorted(LOAD_CALLS) == ["todo-2", "todo-3"]


def candidate(instance_id: str, level=None, resolved=None, status: str = "dirty"):
    """Build one FanoutCandidate carrying only the fields _drop_nested reads."""
    return FanoutCandidate(
        type_name="fanout_widget",
        component_class=FanoutWidget,
        instance_id=instance_id,
        load=None,
        status=status,
        entry=entry("fanout_widget", instance_id),
        resolved=resolved,
        level=level,
    )


def stamped_level(instance_id: str, *children) -> RenderedLevel:
    """A RenderedLevel whose root tag carries data-pjx-id, with children nested."""
    root = f'<div data-pjx-id="{instance_id}">'
    return RenderedLevel(
        segments=[root, *children, "</div>"],
        root_span=(0, len(root)),
        descriptor=FanoutWidget.__pjx_descriptor__,
    )


def reactive_level(
    instance_id: str,
    type_name: str = "quiet_widget",
    load: str | None = None,
    children: tuple = (),
) -> RenderedLevel:
    """A RenderedLevel whose root tag carries the full reactive identity stamp.

    `stamped_level` writes only `data-pjx-id`. The preserve pass also reads
    `data-pjx-type` (the only place a nested level records its owning class)
    and `data-pjx-load`, so these tests need a root tag shaped the way
    `stamp_reactive_root_attrs` shapes a real one.
    """
    attrs = (
        f'data-pjx-id="{instance_id}" data-pjx-type="{type_name}" '
        f'data-pjx-hash="h-{instance_id}"'
    )
    if load is not None:
        attrs += f' data-pjx-load="{load}"'
    root = f"<div {attrs}>"
    return RenderedLevel(
        segments=[root, *children, "</div>"],
        root_span=(0, len(root)),
        descriptor=FanoutWidget.__pjx_descriptor__,
    )


def dirty_with_level(instance_id: str, level: RenderedLevel) -> FanoutCandidate:
    """A dirty candidate carrying a hand-shaped level and the fresh_hash oob_swaps asserts."""
    return dataclasses.replace(
        candidate(instance_id, level=level), fresh_hash="fresh-hash"
    )


def test_drop_nested_drops_a_child_level_nested_in_a_parent_level():
    child = stamped_level("child")
    parent = stamped_level("parent", child)
    with scope():
        survivors = _drop_nested(
            [candidate("parent", level=parent), candidate("child", level=child)]
        )
    assert [c.instance_id for c in survivors] == ["parent"]


def test_drop_nested_keeps_siblings_that_contain_neither_other():
    with scope():
        survivors = _drop_nested(
            [
                candidate("a", level=stamped_level("a")),
                candidate("b", level=stamped_level("b")),
            ]
        )
    assert [c.instance_id for c in survivors] == ["a", "b"]


def test_drop_nested_drops_a_clean_child_whose_resolved_is_a_nested_level():
    child = stamped_level("child")
    parent = stamped_level("parent", child)
    with scope():
        survivors = _drop_nested(
            [
                candidate("parent", level=parent),
                candidate("child", resolved=child, status="clean"),
            ]
        )
    assert [c.instance_id for c in survivors] == ["parent"]


def test_drop_nested_keeps_a_live_instance_candidate_not_found_in_any_tree():
    with scope():
        survivors = _drop_nested(
            [
                candidate("parent", level=stamped_level("parent")),
                candidate("other", resolved=FanoutWidget(id="other"), status="clean"),
            ]
        )
    assert [c.instance_id for c in survivors] == ["parent", "other"]


def test_drop_nested_finds_a_child_declared_as_an_unfilled_child_ref():
    parent = stamped_level(
        "parent", ChildRef(tag="FanoutWidget", attrs={"id": "child"}, inner=None)
    )
    with scope():
        survivors = _drop_nested(
            [candidate("parent", level=parent), candidate("child")]
        )
    assert [c.instance_id for c in survivors] == ["parent"]


def test_drop_nested_collapses_three_levels_to_the_outermost():
    child = stamped_level("child")
    parent = stamped_level("parent", child)
    grandparent = stamped_level("grandparent", parent)
    with scope():
        survivors = _drop_nested(
            [
                candidate("grandparent", level=grandparent),
                candidate("parent", level=parent),
                candidate("child", level=child),
            ]
        )
    assert [c.instance_id for c in survivors] == ["grandparent"]


def test_drop_nested_is_a_no_op_on_empty_and_singleton_lists():
    only = [candidate("a", level=stamped_level("a"))]
    with scope():
        assert _drop_nested([]) == []
        assert _drop_nested(only) == only


def test_drop_nested_scales_over_a_large_mixed_candidate_set():
    """60 candidates: 20 parent/child pairs plus 20 loners, order preserved.

    Large enough that a per-candidate rescan and a two-pass union would
    disagree if the union ever lost or over-collected a tree.
    """
    candidates = []
    expected = []
    for i in range(20):
        child = stamped_level(f"child{i}")
        parent = stamped_level(f"parent{i}", child)
        candidates.append(candidate(f"parent{i}", level=parent))
        candidates.append(candidate(f"child{i}", level=child))
        expected.append(f"parent{i}")
    for i in range(20):
        candidates.append(candidate(f"loner{i}", level=stamped_level(f"loner{i}")))
        expected.append(f"loner{i}")
    with scope():
        survivors = _drop_nested(candidates)
    # Manifest order is parent0, child0, parent1, child1, ... then the loners;
    # dropping the children leaves the parents in that same relative order.
    assert [c.instance_id for c in survivors] == expected
    assert len(survivors) == len({id(c) for c in survivors})


def test_drop_nested_keeps_independent_nesting_groups_isolated():
    """Two unrelated families in one call; neither group's union touches the other."""
    b = stamped_level("b")
    c = stamped_level("c")
    a = stamped_level("a", b, c)
    e = stamped_level("e")
    d = stamped_level("d", e)
    with scope():
        survivors = _drop_nested(
            [
                candidate("a", level=a),
                candidate("b", level=b),
                candidate("c", level=c),
                candidate("d", level=d),
                candidate("e", level=e),
            ]
        )
    assert [c.instance_id for c in survivors] == ["a", "d"]


def test_drop_nested_keeps_a_structureless_candidate_among_large_trees():
    """Absence of a check is never a drop, no matter how much tree surrounds it."""
    deep = stamped_level("deep0")
    for i in range(1, 30):
        deep = stamped_level(f"deep{i}", deep)
    with scope():
        survivors = _drop_nested(
            [
                candidate("deep29", level=deep),
                candidate("no-structure"),
            ]
        )
    assert [c.instance_id for c in survivors] == ["deep29", "no-structure"]


def test_drop_nested_collapses_a_four_level_chain():
    """A > B > C > D, all four candidates: only A survives."""
    d = stamped_level("d")
    c = stamped_level("c", d)
    b = stamped_level("b", c)
    a = stamped_level("a", b)
    with scope():
        survivors = _drop_nested(
            [
                candidate("a", level=a),
                candidate("b", level=b),
                candidate("c", level=c),
                candidate("d", level=d),
            ]
        )
    assert [x.instance_id for x in survivors] == ["a"]


def test_drop_nested_walks_each_candidate_tree_exactly_once(monkeypatch):
    """One `_contained` call per candidate with a level — never one per pair.

    The linear rewrite unions every tree once, then filters; a nested-loop
    implementation would walk trees a quadratic number of times.
    """
    calls: list[int] = []
    real_contained = fanout._contained

    def counting_contained(level):
        calls.append(id(level))
        return real_contained(level)

    monkeypatch.setattr(fanout, "_contained", counting_contained)

    levels = [stamped_level(f"n{i}") for i in range(10)]
    candidates = [candidate(f"n{i}", level=levels[i]) for i in range(10)]
    candidates.append(candidate("no-structure"))
    with scope():
        survivors = _drop_nested(candidates)

    assert len(calls) == 10
    assert len(set(calls)) == 10
    assert [c.instance_id for c in survivors] == [f"n{i}" for i in range(10)] + [
        "no-structure"
    ]


def test_contained_reports_a_nested_reactive_root_with_its_class_and_load_key():
    nested = reactive_level("nested", "fanout_widget", load="todo-9")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    with scope() as session:
        session.nested_react_keys["nested"] = ("todos",)
        ids, objects, nested_roots = fanout._contained(parent, session)
    assert ids == {"nested"}
    assert objects == {id(nested)}
    assert list(nested_roots) == ["nested"]
    record = nested_roots["nested"]
    assert record.level is nested
    assert record.component_class is FanoutWidget
    assert record.react_keys == ("todos",)
    assert record.load_key == "todo-9"


def test_contained_without_a_session_reports_no_react_keys():
    """No session, no map: the id is still found, but nothing claims it is disjoint."""
    nested = reactive_level("nested", "quiet_widget")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    ids, _objects, nested_roots = fanout._contained(parent)
    assert ids == {"nested"}
    assert nested_roots["nested"].react_keys is None
    assert nested_roots["nested"].component_class is QuietWidget


def test_contained_reports_no_class_for_a_nested_root_without_a_pjx_type():
    """An unstamped nested root resolves to no class, so nothing can be decided about it."""
    nested = stamped_level("nested")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    _ids, _objects, nested_roots = fanout._contained(parent)
    assert nested_roots["nested"].component_class is None
    assert nested_roots["nested"].load_key is None


def nested_tag_of(body: str, instance_id: str) -> str:
    """The opening tag of the nested root with this id, out of a serialized body."""
    start = body.index(f'<div data-pjx-id="{instance_id}"')
    return body[start : body.index(">", start) + 1]


def test_a_disjoint_nested_region_is_stamped_with_hx_preserve():
    nested = reactive_level("nested", "quiet_widget")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    with scope() as session:
        session.nested_react_keys["nested"] = ("other",)
        body = str(oob_swaps([dirty_with_level("parent", parent)], {"todos"}, session))
    assert 'hx-preserve="true"' in nested_tag_of(body, "nested")
    parent_tag = nested_tag_of(body, "parent")
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='parent']\"" in parent_tag
    assert 'data-pjx-hash="fresh-hash"' in parent_tag
    assert "hx-preserve" not in parent_tag


def test_a_regions_own_fragment_never_carries_the_stamp():
    """Step 3 only ever touches nested ids inside another candidate's fragment."""
    own = reactive_level("nested", "quiet_widget")
    with scope() as session:
        session.nested_react_keys["nested"] = ("other",)
        body = str(oob_swaps([dirty_with_level("nested", own)], {"todos"}, session))
    assert "hx-preserve" not in body
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='nested']\"" in body


def test_a_nested_root_with_no_recorded_react_keys_is_left_byte_identical():
    """Absence of information is never disjointness: the fragment is today's exactly."""
    nested = reactive_level("nested", "quiet_widget")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    baseline_nested = reactive_level("nested", "quiet_widget")
    baseline_parent = reactive_level(
        "parent", "fanout_widget", children=(baseline_nested,)
    )
    with scope() as session:
        stamped = str(
            oob_swaps([dirty_with_level("parent", parent)], {"todos"}, session)
        )
        baseline = str(oob_swaps([dirty_with_level("parent", baseline_parent)]))
    assert "hx-preserve" not in stamped
    assert stamped == baseline


def test_stamping_a_nested_root_leaves_its_identity_attrs_untouched():
    """The first caller to stamp a *nested* root: no RootStampCollisionError."""
    nested = reactive_level("nested", "quiet_widget", load="k-1")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    with scope() as session:
        session.nested_react_keys["nested"] = ("other",)
        body = str(oob_swaps([dirty_with_level("parent", parent)], {"todos"}, session))
    tag = nested_tag_of(body, "nested")
    assert 'data-pjx-id="nested"' in tag
    assert 'data-pjx-type="quiet_widget"' in tag
    assert 'data-pjx-hash="h-nested"' in tag
    assert 'data-pjx-load="k-1"' in tag
    assert 'hx-preserve="true"' in tag


def test_a_class_opting_out_of_retention_is_never_stamped():
    nested = reactive_level("nested", "owned_widget")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    with scope() as session:
        session.nested_react_keys["nested"] = ("other",)
        body = str(oob_swaps([dirty_with_level("parent", parent)], {"todos"}, session))
    assert "hx-preserve" not in body


def test_a_nested_root_that_is_itself_a_candidate_is_never_stamped():
    """Belt and braces, asserted directly.

    A real walk cannot produce this shape — a candidate's own keys always match
    the dirtied set that made it one — so the guard is driven by a hand-built
    candidate list whose session map deliberately disagrees with that.
    """
    nested = reactive_level("nested", "quiet_widget")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    with scope() as session:
        session.nested_react_keys["nested"] = ("other",)
        body = str(
            oob_swaps(
                [
                    dirty_with_level("parent", parent),
                    dirty_with_level("nested", nested),
                ],
                {"todos"},
                session,
            )
        )
    assert "hx-preserve" not in body


def test_a_nested_root_dirtied_by_the_dynamic_key_form_is_not_stamped():
    """The `key:load_key` form is folded in from the tag's own data-pjx-load."""
    nested = reactive_level("nested", "fanout_widget", load="9")
    parent = reactive_level("parent", "fanout_widget", children=(nested,))
    with scope() as session:
        session.nested_react_keys["nested"] = ("todos",)
        body = str(
            oob_swaps([dirty_with_level("parent", parent)], {"todos:9"}, session)
        )
    assert "hx-preserve" not in body


def test_parent_and_child_dirtied_by_one_request_yield_no_preserve_anywhere():
    """Regression guard for the failure the app's static-attribute workaround hit."""
    child = reactive_level("child", "fanout_widget")
    parent = reactive_level("parent", "fanout_widget", children=(child,))
    with scope() as session:
        session.nested_react_keys["parent"] = ("todos",)
        session.nested_react_keys["child"] = ("todos",)
        survivors = _drop_nested(
            [dirty_with_level("parent", parent), dirty_with_level("child", child)]
        )
        body = str(oob_swaps(survivors, {"todos"}, session))
    assert [c.instance_id for c in survivors] == ["parent"]
    assert "hx-preserve" not in body


def test_mounted_ids_in_extracts_both_quote_styles():
    html = "<div data-pjx-id=\"alpha\"><span data-pjx-id='beta'>x</span></div>"
    assert _mounted_ids_in(html) == {"alpha", "beta"}


def test_mounted_ids_in_answers_empty_for_markup_without_ids_and_for_none():
    assert _mounted_ids_in("<div>plain</div>") == set()
    assert _mounted_ids_in("") == set()
    assert _mounted_ids_in(None) == set()


def test_entry_whose_id_is_in_the_primary_response_is_excluded_before_any_load():
    with scope():
        candidates = walk_manifest(
            [entry("fanout_widget", "a", load="todo-1")],
            {"todos"},
            primary_html='<div data-pjx-id="a">already swapped</div>',
        )
    assert candidates == []
    # The exclusion is the first filter, not a late one: the entry never paid
    # for a load or a render.
    assert LOAD_CALLS == []


def test_entry_absent_from_the_primary_response_resolves_normally():
    with scope():
        [candidate_] = walk_manifest(
            [entry("fanout_widget", "a", load="todo-1")],
            {"todos"},
            primary_html='<div data-pjx-id="somewhere-else">x</div>',
        )
    assert candidate_.instance_id == "a"
    assert candidate_.status == "dirty"
    assert LOAD_CALLS == ["todo-1"]


def test_walk_manifest_without_primary_html_is_unchanged():
    manifest = [
        entry("fanout_widget", "a", load="todo-1"),
        entry("fanout_widget", "b", load="todo-2"),
    ]
    with scope():
        omitted = [
            (c.instance_id, c.status) for c in walk_manifest(manifest, {"todos"})
        ]
    LOAD_CALLS.clear()
    with scope():
        explicit_none = [
            (c.instance_id, c.status)
            for c in walk_manifest(manifest, {"todos"}, primary_html=None)
        ]
    assert omitted == explicit_none == [("a", "dirty"), ("b", "dirty")]


def test_primary_exclusion_and_nesting_dedup_compose_in_one_walk(monkeypatch):
    """One entry dropped by the primary, a separate pair still deduped by nesting."""
    child = stamped_level("child")
    parent = stamped_level("parent", child)
    levels = {"parent": parent, "child": child}

    def fake_build_dirty(cls, instance_id, load, session):
        return cls(id=instance_id), levels[instance_id]

    monkeypatch.setattr("pyjinhx.reactive.fanout._build_dirty", fake_build_dirty)
    manifest = [
        entry("fanout_widget", "in-primary", load="todo-0"),
        entry("fanout_widget", "parent", load="todo-1"),
        entry("fanout_widget", "child", load="todo-2"),
    ]
    with scope():
        registry.register_instance(FanoutWidget.__name__, "in-primary", "e0")
        registry.register_instance(FanoutWidget.__name__, "parent", "e1")
        registry.register_instance(FanoutWidget.__name__, "child", "e2")
        candidates = walk_manifest(
            manifest,
            {"todos"},
            primary_html='<section data-pjx-id="in-primary"></section>',
        )
    assert [c.instance_id for c in candidates] == ["parent"]


def missing_candidate(instance_id: str, status: str = "missing") -> FanoutCandidate:
    """A FanoutCandidate shaped exactly as walk_manifest builds one for a gone region."""
    return FanoutCandidate(
        type_name="fanout_widget",
        component_class=FanoutWidget,
        instance_id=instance_id,
        load="todo-1",
        status=status,
        entry=entry("fanout_widget", instance_id, load="todo-1"),
    )


def test_delete_swap_for_a_plain_id_is_a_bare_oob_delete_div():
    assert (
        delete_swap(missing_candidate("todo-list"))
        == "<div hx-swap-oob=\"delete:[data-pjx-id='todo-list']\"></div>"
    )


def test_delete_swap_escapes_a_single_quote_in_the_id():
    fragment = delete_swap(missing_candidate("it's-here"))
    assert "delete:[data-pjx-id='it\\'s-here']" in fragment
    # The selector's quoting stays balanced: exactly the opening and closing
    # quote are unescaped, so nothing after the id leaks into the selector.
    assert fragment.count("'") - fragment.count("\\'") == 2


def test_delete_swap_escapes_a_backslash_in_the_id():
    fragment = delete_swap(missing_candidate("back\\slash"))
    assert "delete:[data-pjx-id='back\\\\slash']" in fragment


def test_delete_swap_escapes_a_backslash_before_a_quote_without_unescaping_it():
    # The order-sensitive case: "\\'" must become "\\\\\\'", never "\\\\'",
    # which would end the selector's quoted value early.
    fragment = delete_swap(missing_candidate("a\\'b"))
    assert "delete:[data-pjx-id='a\\\\\\'b']" in fragment


@pytest.mark.parametrize("status", ["clean", "dirty"])
def test_delete_swap_rejects_a_non_missing_candidate(status):
    with pytest.raises(ValueError, match=status):
        delete_swap(missing_candidate("a", status=status))


def test_delete_swap_of_an_empty_id_is_still_a_fragment():
    # walk_manifest coerces an entry with no id to "", and that is not this
    # function's problem to diagnose — it emits the selector it was given.
    assert (
        delete_swap(missing_candidate(""))
        == "<div hx-swap-oob=\"delete:[data-pjx-id='']\"></div>"
    )


def test_a_gone_region_walks_to_a_delete_fragment_without_loading_anything(
    monkeypatch,
):
    calls: list[tuple] = []
    monkeypatch.setattr(
        registry, "register_instance", lambda *a, **kw: calls.append((a, kw))
    )
    GONE_KEYS.add("todo-1")
    with scope():
        [candidate_] = walk_manifest(
            [entry("fanout_widget", "gone-1", load="todo-1")], {"todos"}
        )
    assert candidate_.status == "missing"
    assert (
        delete_swap(candidate_)
        == "<div hx-swap-oob=\"delete:[data-pjx-id='gone-1']\"></div>"
    )
    # Establishing the region is gone costs the one failed load() and nothing
    # more: no render, and no registry write, on the whole path from manifest
    # entry to delete fragment.
    assert LOAD_CALLS == ["todo-1"]
    assert candidate_.level is None
    assert calls == []


def _dirty_candidate(instance_id: str) -> FanoutCandidate:
    """A real dirty FanoutCandidate, built the same way the walk builds one."""
    with scope():
        registry.register_instance(FanoutWidget.__name__, instance_id, "resolved-entry")
        [c] = walk_manifest(
            [entry("fanout_widget", instance_id, load="todo-1")], {"todos"}
        )
    return c


def _missing_candidate(instance_id: str) -> FanoutCandidate:
    return missing_candidate(instance_id)


def _clean_candidate(instance_id: str) -> FanoutCandidate:
    return candidate(instance_id, status="clean")


def test_oob_swaps_mixes_dirty_missing_and_clean():
    dirty = _dirty_candidate("a")
    missing = _missing_candidate("b")
    clean = _clean_candidate("c")

    body = oob_swaps([dirty, missing, clean])

    fragments = body.split("\n")
    assert len(fragments) == 2
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in fragments[0]
    assert "data-pjx-hash=" in fragments[0]
    assert fragments[1] == "<div hx-swap-oob=\"delete:[data-pjx-id='b']\"></div>"


def test_oob_swap_attr_lands_once_in_the_root_tag_beside_the_id_and_hash():
    """v0.x parity: hx-swap-oob is folded into the same root-tag splice, not appended."""
    with scope():
        candidate = _dirty_candidate("a")
        out = str(oob_swaps([candidate]))
    assert out.count("hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"") == 1
    first_tag = out[: out.index(">") + 1]
    assert "hx-swap-oob=" in first_tag
    assert f'data-pjx-hash="{candidate.fresh_hash}"' in first_tag


def test_walk_manifest_runs_the_nesting_dedup_on_its_survivors(monkeypatch):
    """The pass is wired into the walk, not just importable."""
    seen_calls: list[int] = []
    original = _drop_nested

    def spy(candidates):
        seen_calls.append(len(candidates))
        return original(candidates)

    monkeypatch.setattr("pyjinhx.reactive.fanout._drop_nested", spy)
    with scope():
        walk_manifest(
            [
                entry("fanout_widget", "a", load="t1"),
                entry("fanout_widget", "b", load="t2"),
            ],
            {"todos"},
        )
    assert seen_calls == [2]


def test_one_walk_composes_every_status_gate_and_nesting_drop(monkeypatch):
    """The whole decision matrix, in a single manifest and a single walk.

    Every prior test isolates one filter; this one is the composed contract:
    clean, dirty-survives, dirty-gated-out, missing, nested-child-dropped and
    a no-tree survivor all decided in one pass, asserted as one ordered list.
    """
    child = stamped_level("child")
    parent = stamped_level("parent", child)
    real_build = fanout._build_dirty

    def build(cls, instance_id, load, session):
        instance, level = real_build(cls, instance_id, load, session)
        # Only the parent/child pair needs a hand-shaped tree; every other
        # dirty entry keeps its real render, so the hash gate stays honest.
        return instance, {"parent": parent, "child": child}.get(instance_id, level)

    monkeypatch.setattr(fanout, "_build_dirty", build)
    GONE_KEYS.add("todo-4")
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        for instance_id in ("a", "same", "moved", "parent", "child", "lonely"):
            registry.register_instance(FanoutWidget.__name__, instance_id, "entry")
        manifest = [
            entry("fanout_widget", "a", load="todo-1"),  # clean: cache hit
            entry(
                "fanout_widget", "same", load="todo-2", hash_=fresh_hash_for("todo-2")
            ),  # dirty, gated out
            entry(
                "fanout_widget", "moved", load="todo-3", hash_="stale"
            ),  # dirty, survives
            entry("fanout_widget", "gone", load="todo-4"),  # missing
            entry(
                "fanout_widget", "parent", load="todo-5", hash_="stale"
            ),  # dirty ancestor
            entry(
                "fanout_widget", "child", load="todo-6", hash_="stale"
            ),  # nested, dropped
            entry(
                "fanout_widget", "lonely", load="todo-7", hash_="stale"
            ),  # no containing tree
        ]
        candidates = walk_manifest(manifest, {"todos"})

    assert [(c.instance_id, c.status) for c in candidates] == [
        ("a", "clean"),
        ("moved", "dirty"),
        ("gone", "missing"),
        ("parent", "dirty"),
        ("lonely", "dirty"),
    ]
    # "same" is dropped by the gate, not relabelled clean; "child" is dropped
    # by the nesting pass, not by the gate — both absences are load-bearing.
    assert "same" not in {c.instance_id for c in candidates}
    assert "child" not in {c.instance_id for c in candidates}


def test_oob_swaps_over_a_real_walk_emits_only_outerhtml_and_delete(monkeypatch):
    """ADR 0001: outerHTML for each dirty survivor, delete for each missing, nothing else."""
    GONE_KEYS.add("todo-3")
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        registry.register_instance(FanoutWidget.__name__, "a", "entry-a")
        registry.register_instance(FanoutWidget.__name__, "moved", "entry-moved")
        candidates = walk_manifest(
            [
                entry("fanout_widget", "a", load="todo-1"),
                entry("fanout_widget", "moved", load="todo-2", hash_="stale"),
                entry("fanout_widget", "gone", load="todo-3"),
            ],
            {"todos"},
        )
        body = oob_swaps(candidates)

    swaps = re.findall(r'hx-swap-oob="([^:]+):', body)
    assert swaps == ["outerHTML", "delete"]
    assert "[data-pjx-id='moved']" in body
    assert "[data-pjx-id='gone']" in body
    # The clean region emits nothing at all — not an empty fragment, not a
    # no-op swap; its id must not appear anywhere in the body.
    assert "'a'" not in body


def test_primary_exclusion_skips_the_entry_before_any_registry_resolve(monkeypatch):
    """The cheapest filter runs first: an excluded id costs no resolve, no load."""
    resolved_ids: list[str] = []
    real_resolve = registry.resolve

    def spy(class_name, instance_id):
        resolved_ids.append(instance_id)
        return real_resolve(class_name, instance_id)

    monkeypatch.setattr(registry, "resolve", spy)
    with scope():
        registry.register_instance(FanoutWidget.__name__, "in-primary", "entry-0")
        registry.register_instance(FanoutWidget.__name__, "elsewhere", "entry-1")
        candidates = walk_manifest(
            [
                entry("fanout_widget", "in-primary", load="todo-1"),
                entry("fanout_widget", "elsewhere", load="todo-2", hash_="stale"),
            ],
            {"todos"},
            primary_html='<section data-pjx-id="in-primary"></section>',
        )

    assert [c.instance_id for c in candidates] == ["elsewhere"]
    assert resolved_ids == ["elsewhere"]
    assert LOAD_CALLS == ["todo-2"]


def test_dirty_path_uses_an_explicit_session_and_the_ambient_one_alike():
    """state_hash depends on the render, so both session resolution paths must work."""
    manifest = [entry("fanout_widget", "s", load="todo-1", hash_="stale")]
    with scope():
        registry.register_instance(FanoutWidget.__name__, "s", "entry-s")
        [ambient] = walk_manifest(manifest, {"todos"})

    # `registry.resolve`/`register_instance` are backed by a ContextVar that
    # only exists inside `request_scope()` — calling them with no scope at all
    # doesn't skip the ambient session, it silently drops the registration and
    # then fails to resolve, so there's no way to exercise the "explicit
    # session, no scope" path literally. Instead: a second, distinct ambient
    # scope proves the explicit `session=` argument is actually taken and not
    # merely tolerated alongside a correct ambient one.
    with request_scope():
        registry.register_instance(FanoutWidget.__name__, "s", "entry-s")
        [explicit] = walk_manifest(manifest, {"todos"}, session=RenderSession())

    assert ambient.status == explicit.status == "dirty"
    assert ambient.fresh_hash == explicit.fresh_hash == fresh_hash_for("todo-1")


class IntKeyedWidget(ReactiveComponent, react=("todos",)):
    """A component whose PjxKey field is an `int`, like the todo example's row.

    `data-pjx-load` is an HTML attribute, so this class's key round-trips
    through the client as a string and must arrive back at `load()` as an int.
    """

    row_id: Annotated[int, PjxKey()] = 0
    title: str = ""

    @classmethod
    def load(cls, row_id: int) -> "IntKeyedWidget":
        INT_KEY_LOAD_ARGS.append(row_id)
        # A dict keyed by int, exactly like the demo store: a str key misses.
        titles = {1: "first", 2: "second"}
        return cls(row_id=row_id, title=titles.get(row_id, ""))


INT_KEY_LOAD_ARGS: list[object] = []


def test_a_string_load_arg_reaches_load_as_the_declared_int(tmp_path):
    """The manifest's `"1"` must arrive at load() as `1`, not `"1"`.

    Regression: a rebuilt row rendered with every field at its default because
    `load()` looked its key up in an int-keyed store and missed.
    """
    INT_KEY_LOAD_ARGS.clear()
    template = tmp_path / "int_keyed_widget.pjx"
    template.write_text("<div>{{ title }}</div>")
    discovery.build_registry(tmp_path, [IntKeyedWidget])
    IntKeyedWidget.__pjx_descriptor__ = dataclasses.replace(
        IntKeyedWidget.__pjx_descriptor__, template_path=template
    )
    with scope():
        [candidate] = walk_manifest(
            [entry("int_keyed_widget", "row-1", load="1")], {"todos"}
        )

    assert INT_KEY_LOAD_ARGS == [1]
    assert candidate.status == "dirty"
    assert candidate.instance is not None
    assert cast(IntKeyedWidget, candidate.instance).title == "first"


def _entry(
    entry_id: str, type_name: str, load: str | None, hash_value: str | None = None
):
    """One manifest entry shaped the way `MountedManifest.parse()` emits them."""
    entry: dict[str, object] = {"id": entry_id, "type": type_name, "load": load}
    if hash_value is not None:
        entry["hash"] = hash_value
    return entry


def test_walk_manifest_mixed_manifest_parity():
    """One manifest exercising every drop reason resolves to one ordered survivor list."""
    GONE_KEYS.add("gone")
    primary_html = '<div data-pjx-id="in-primary"></div>'
    manifest = [
        # Dropped: already carried by the primary response.
        _entry("in-primary", "fanout_widget", "a"),
        # Dropped: unknown tag.
        _entry("unknown", "no_such_widget", "a"),
        # Dropped: known tag, non-reactive class.
        _entry("plain", "plain_widget", None),
        # Dropped: reactive, but no dirtied key names it.
        _entry("quiet", "quiet_widget", None),
        # Survives: dirty build.
        _entry("first", "fanout_widget", "a"),
        # Dropped: same (type, load key) as "first".
        _entry("dup", "fanout_widget", "a"),
        # Survives: missing, load() refuses to build "gone".
        _entry("missing", "fanout_widget", "gone"),
        # Survives: dirty build under a different load key.
        _entry("second", "fanout_widget", "b"),
    ]
    with request_scope():
        candidates = walk_manifest(manifest, ["todos"], primary_html=primary_html)

    assert [(c.instance_id, c.status) for c in candidates] == [
        ("first", "dirty"),
        ("missing", "missing"),
        ("second", "dirty"),
    ]
    assert [c.type_name for c in candidates] == ["fanout_widget"] * 3
    assert [c.load for c in candidates] == ["a", "gone", "b"]
    assert all(c.component_class is FanoutWidget for c in candidates)
    assert candidates[0].fresh_hash is not None
    assert candidates[1].fresh_hash is None
    assert candidates[1].level is None and candidates[1].instance is None
    assert candidates[2].fresh_hash is not None
    # E10: the dedup'd "dup" entry must not have bought a second load().
    assert sorted(LOAD_CALLS) == ["a", "b", "gone"]


def test_walk_manifest_hash_gate_drops_unchanged_region():
    """A dirty entry whose fresh hash equals the reported one is dropped."""
    with request_scope():
        built = walk_manifest([_entry("only", "fanout_widget", "a")], ["todos"])
    fresh = built[0].fresh_hash
    assert fresh is not None
    # A fresh request_scope() so the first call's load cache does not turn
    # this second call's entry "clean" before the hash gate ever runs.
    with request_scope():
        gated = walk_manifest([_entry("only", "fanout_widget", "a", fresh)], ["todos"])
    assert gated == []


def test_walk_manifest_missing_entry_does_not_affect_siblings():
    """One entry's failed load leaves every sibling's outcome untouched."""
    GONE_KEYS.add("gone")
    manifest = [
        _entry("a", "fanout_widget", "a"),
        _entry("bad", "fanout_widget", "gone"),
        _entry("c", "fanout_widget", "c"),
    ]
    with request_scope():
        candidates = walk_manifest(manifest, ["todos"])

    assert [(c.instance_id, c.status) for c in candidates] == [
        ("a", "dirty"),
        ("bad", "missing"),
        ("c", "dirty"),
    ]
    assert candidates[0].instance is not None
    assert candidates[2].instance is not None
    assert sorted(LOAD_CALLS) == ["a", "c", "gone"]


def test_walk_manifest_non_lookup_error_propagates():
    """A worker's non-LookupError exception reaches the caller unswallowed."""

    def boom(pjx_key: str):
        raise RuntimeError(f"boom:{pjx_key}")

    with request_scope(), pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            FanoutWidget, "load", classmethod(lambda cls, pjx_key: boom(pjx_key))
        )
        with pytest.raises(RuntimeError, match="boom:a"):
            walk_manifest([_entry("a", "fanout_widget", "a")], ["todos"])


def test_filter_pass_keeps_manifest_order_and_dedups():
    """The filter pass yields surviving, deduped items tagged with their index."""
    manifest = [
        _entry("in-primary", "fanout_widget", "a"),
        _entry("unknown", "no_such_widget", "a"),
        _entry("quiet", "quiet_widget", None),
        _entry("first", "fanout_widget", "a"),
        _entry("dup", "fanout_widget", "a"),
        _entry("second", "fanout_widget", "b"),
    ]
    with request_scope():
        items = fanout._filter_pass(manifest, {"todos"}, {"in-primary"})

    assert [(i.index, i.instance_id, i.load_key) for i in items] == [
        (3, "first", "a"),
        (5, "second", "b"),
    ]
    assert all(i.component_class is FanoutWidget for i in items)
    assert all(i.clean is False for i in items)
    # The filter pass must not have loaded or rendered anything.
    assert LOAD_CALLS == []


def test_build_pass_results_are_keyed_by_manifest_index():
    """Each dirty item's build result comes back under its manifest position."""
    GONE_KEYS.add("gone")
    manifest = [
        _entry("quiet", "quiet_widget", None),
        _entry("a", "fanout_widget", "a"),
        _entry("bad", "fanout_widget", "gone"),
    ]
    with request_scope() as session:
        items = fanout._filter_pass(manifest, {"todos"}, set())
        results = fanout._build_pass(items, session)

    assert sorted(results) == [1, 2]
    assert results[1].missing is False
    assert results[1].instance is not None and results[1].level is not None
    assert results[2].missing is True
    assert results[2].instance is None and results[2].level is None


def test_reduce_pass_restores_manifest_order():
    """Candidates come back in work-item order, whatever order builds finished in."""
    manifest = [
        _entry("a", "fanout_widget", "a"),
        _entry("b", "fanout_widget", "b"),
    ]
    with request_scope() as session:
        items = fanout._filter_pass(manifest, {"todos"}, set())
        built = fanout._build_pass(items, session)
        # Rebuild the mapping back-to-front: the reduce pass must key off the
        # work items, never off insertion order of the results dict.
        shuffled = {index: built[index] for index in sorted(built, reverse=True)}
        candidates = fanout._reduce_pass(items, shuffled)

    assert [c.instance_id for c in candidates] == ["a", "b"]
    assert [c.status for c in candidates] == ["dirty", "dirty"]


def test_build_pass_reduce_pass_order_survives_real_thread_interleaving():
    """Ten real threaded builds finishing back-to-front still reduce in manifest order.

    The sleeps are inverted against manifest position, so the last item's load
    returns first and the first item's returns last. A reduce pass that keyed
    off the results dict's insertion order — or off completion order — would
    hand back a reversed list here while still passing the two-item guards
    above, which is the hole this test exists to cover.
    """
    keys = [f"k{i}" for i in range(10)]
    GONE_KEYS.add("k4")
    finished: list[str] = []
    finished_lock = threading.Lock()

    def jittered_load(cls, pjx_key: str):
        # Later manifest positions sleep least, so completion order comes back
        # roughly reversed against submission order.
        time.sleep((10 - int(pjx_key[1:])) * 0.01)
        with finished_lock:
            finished.append(pjx_key)
        if pjx_key in GONE_KEYS:
            raise LookupError(f"no widget for {pjx_key!r}")
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")

    manifest = [_entry(key, "fanout_widget", key) for key in keys]
    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(FanoutWidget, "load", classmethod(jittered_load))
        items = fanout._filter_pass(manifest, {"todos"}, set())
        built = fanout._build_pass(items, session)
        candidates = fanout._reduce_pass(items, built)

    # The interleaving actually happened — otherwise the ordering assertion
    # below proves nothing.
    assert finished != keys
    assert len(finished) == 10
    assert [c.instance_id for c in candidates] == keys
    assert [c.status for c in candidates] == (
        ["dirty"] * 4 + ["missing"] + ["dirty"] * 5
    )
    missing = candidates[4]
    assert missing.instance is None
    assert missing.level is None
    assert missing.resolved is None
    assert missing.fresh_hash is None
    assert all(c.instance is not None for c in candidates if c.status == "dirty")
    assert all(c.fresh_hash is not None for c in candidates if c.status == "dirty")


def test_a_raising_future_abandons_the_whole_pass():
    """A non-LookupError leaves no partial result set behind — the pass is all or nothing.

    `_reduce_pass` indexes `built[item.index]` for every non-clean item, so a
    half-filled dict would only turn a loader bug into a KeyError somewhere
    else. The build pass hands back one complete mapping or it raises; the
    siblings that already finished are deliberately dropped on the floor.
    """
    manifest = [
        _entry("a", "fanout_widget", "a"),
        _entry("boom", "fanout_widget", "boom"),
        _entry("c", "fanout_widget", "c"),
    ]

    def exploding_load(cls, pjx_key: str):
        if pjx_key == "boom":
            raise RuntimeError(f"boom:{pjx_key}")
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")

    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(FanoutWidget, "load", classmethod(exploding_load))
        items = fanout._filter_pass(manifest, {"todos"}, set())
        with pytest.raises(RuntimeError, match="boom:boom") as caught:
            fanout._build_pass(items, session)

    # The loader's own exception travels, not a wrapper: a caller upstack that
    # knows what its load() raises must still be able to catch it by type.
    assert type(caught.value) is RuntimeError
    # And the pass yields no value at all — there is no partial mapping to
    # inspect, by design.
    assert caught.value.args == ("boom:boom",)


def test_build_pass_skips_the_pool_when_every_class_measured_too_cheap():
    """A pass whose classes all load cheaply builds inline, with no pool at all."""
    note_load_cost(FanoutWidget, 0.0)
    manifest = [
        entry("fanout_widget", "a", load="a"),
        entry("fanout_widget", "b", load="b"),
    ]
    built_on: list[str] = []

    def recording_load(cls, pjx_key: str):
        built_on.append(threading.current_thread().name)
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")

    def no_pool(*args, **kwargs):
        raise AssertionError("the too-cheap path must not build a ThreadPoolExecutor")

    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(FanoutWidget, "load", classmethod(recording_load))
        patch.setattr(fanout, "ThreadPoolExecutor", no_pool)
        items = fanout._filter_pass(manifest, {"todos"}, set())
        built = fanout._build_pass(items, session)

    assert sorted(built) == [0, 1]
    assert all(result.missing is False for result in built.values())
    assert all(result.instance is not None for result in built.values())
    assert built_on == [threading.current_thread().name] * 2


def test_build_pass_threads_a_class_nobody_measured():
    """An unmeasured class keeps the pool: the verdict is earned, never assumed."""
    manifest = [entry("fanout_widget", "a", load="a")]
    pools: list[int] = []
    real_pool = fanout.ThreadPoolExecutor

    def counting_pool(*args, **kwargs):
        pools.append(1)
        return real_pool(*args, **kwargs)

    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(fanout, "ThreadPoolExecutor", counting_pool)
        items = fanout._filter_pass(manifest, {"todos"}, set())
        built = fanout._build_pass(items, session)

    assert pools == [1]
    assert sorted(built) == [0]
    assert built[0].missing is False


def test_build_pass_threads_when_only_some_classes_are_too_cheap():
    """One costly class in the pass is enough to keep every item on the pool."""
    note_load_cost(FanoutWidget, 0.0)
    manifest = [
        entry("fanout_widget", "a", load="a"),
        entry("loud_widget", "q", load="q"),
    ]
    pools: list[int] = []
    real_pool = fanout.ThreadPoolExecutor

    def counting_pool(*args, **kwargs):
        pools.append(1)
        return real_pool(*args, **kwargs)

    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(fanout, "ThreadPoolExecutor", counting_pool)
        items = fanout._filter_pass(manifest, {"todos"}, set())
        built = fanout._build_pass(items, session)

    assert pools == [1]
    assert sorted(built) == [0, 1]
    assert all(result.missing is False for result in built.values())


def test_build_pass_sequential_path_still_proves_absence():
    """A LookupError on the inline path lands as a missing result, not an escape."""
    note_load_cost(FanoutWidget, 0.0)
    GONE_KEYS.add("gone")
    manifest = [
        entry("fanout_widget", "a", load="a"),
        entry("fanout_widget", "bad", load="gone"),
    ]

    def no_pool(*args, **kwargs):
        raise AssertionError("the too-cheap path must not build a ThreadPoolExecutor")

    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(fanout, "ThreadPoolExecutor", no_pool)
        items = fanout._filter_pass(manifest, {"todos"}, set())
        built = fanout._build_pass(items, session)

    assert built[0].missing is False
    assert built[1].missing is True
    assert built[1].instance is None and built[1].level is None


def _candidate_shape(candidate: FanoutCandidate) -> tuple:
    """One candidate reduced to the values two builds of it must agree on.

    ``instance`` is compared by its dumped fields minus ``id`` rather than by
    identity or model equality: ``id`` is auto-generated per build, so two
    equally correct builds of the same region can never share it — which is
    exactly why ``state_hash()`` excludes it too. ``level`` is compared only
    for presence, because a RenderedLevel holds the class descriptor object
    and its own segment objects, and only the fact that a render happened is
    a cross-path invariant.
    """
    instance = candidate.instance
    return (
        candidate.type_name,
        candidate.component_class,
        candidate.instance_id,
        candidate.load,
        candidate.status,
        candidate.entry,
        candidate.fresh_hash,
        None if instance is None else type(instance),
        None if instance is None else instance.model_dump(exclude={"id"}),
        candidate.level is None,
    )


def test_build_and_reduce_pass_parity_between_sequential_and_threaded_paths():
    """The same manifest yields the same candidates on the pool and inline.

    The threaded run goes first because a class's cost verdict is decided once
    per process and never revisited: measuring it here would let the machine's
    speed, not the test, choose the second run's path. Patching out the
    measurement keeps FanoutWidget unmeasured — and therefore threaded — until
    the test itself notes a zero cost for the inline run.
    """
    GONE_KEYS.add("gone")

    def manifest() -> list[dict]:
        return [
            entry("fanout_widget", "a", load="a"),
            entry("fanout_widget", "bad", load="gone"),
            entry("fanout_widget", "c", load="c"),
        ]

    pools: list[int] = []
    real_pool = fanout.ThreadPoolExecutor

    def counting_pool(*args, **kwargs):
        pools.append(1)
        return real_pool(*args, **kwargs)

    def no_pool(*args, **kwargs):
        raise AssertionError("the too-cheap path must not build a ThreadPoolExecutor")

    # Run B: nobody has measured FanoutWidget, so the pass takes the pool.
    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(fanout, "ThreadPoolExecutor", counting_pool)
        patch.setattr(fanout, "note_load_cost", lambda cls, cost_us: None)
        items = fanout._filter_pass(manifest(), {"todos"}, set())
        built = fanout._build_pass(items, session)
        threaded = fanout._reduce_pass(items, built)

    assert pools == [1]

    # Run A: the same manifest, in a fresh request scope so Run B's load cache
    # cannot report anything clean, with the class now measured as too cheap.
    note_load_cost(FanoutWidget, 0.0)
    with request_scope() as session, pytest.MonkeyPatch.context() as patch:
        patch.setattr(fanout, "ThreadPoolExecutor", no_pool)
        items = fanout._filter_pass(manifest(), {"todos"}, set())
        built = fanout._build_pass(items, session)
        sequential = fanout._reduce_pass(items, built)

    assert pools == [1]
    assert [candidate.instance_id for candidate in sequential] == ["a", "bad", "c"]
    assert [candidate.status for candidate in sequential] == [
        "dirty",
        "missing",
        "dirty",
    ]
    assert len(sequential) == len(threaded)
    assert [_candidate_shape(candidate) for candidate in sequential] == [
        _candidate_shape(candidate) for candidate in threaded
    ]


def test_module_never_registers_instances():
    """Fan-out stays read-only against the instance registry (ADR 0009 E7).

    The module's own docstrings talk *about* ``register_instance`` while
    explaining they never call it, so a bare substring check would trip on
    its own prose. Looking for the call shape is what actually proves it.
    """
    source = pathlib.Path(fanout.__file__).read_text()
    assert "register_instance(" not in source


def test_a_workers_cache_write_lands_in_the_requests_store():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        walk_manifest([entry("fanout_widget", "a", load="todo-1")], {"todos"})
        # The load ran on a pool worker; its memo wrap's cache_put must have
        # mutated the very dict this request's context still points at.
        assert cache_has(FanoutWidget, "todo-1") is True
        assert LOAD_CALLS == ["todo-1"]


def test_a_second_walk_reads_the_workers_cache_entry_as_clean():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        walk_manifest([entry("fanout_widget", "a", load="todo-1")], {"todos"})
        LOAD_CALLS.clear()
        [candidate] = walk_manifest(
            [entry("fanout_widget", "a", load="todo-1")], {"todos"}
        )
        assert candidate.status == "clean"
        assert LOAD_CALLS == []


def test_current_session_inside_a_worker_is_the_requests_session():
    with scope() as session:
        registry.register_instance(SpyWidget.__name__, "a", "resolved-entry")
        walk_manifest([entry("spy_widget", "a", load="todo-1")], {"todos"})
        assert SEEN_SESSIONS == [session]
        assert isinstance(session, RenderSession)


def test_get_load_context_inside_a_worker_is_the_requests_load_context():
    app_context = object()
    with request_scope(load_context=app_context):
        registry.register_instance(SpyWidget.__name__, "a", "resolved-entry")
        walk_manifest([entry("spy_widget", "a", load="todo-1")], {"todos"})
        assert SEEN_LOAD_CONTEXTS == [app_context]


def test_every_workers_cache_write_lands_when_the_pool_has_several_workers():
    with scope():
        manifest = [entry("spy_widget", f"row-{n}", load=f"todo-{n}") for n in range(4)]
        for n in range(4):
            registry.register_instance(SpyWidget.__name__, f"row-{n}", None)
        candidates = walk_manifest(manifest, {"todos"})
        assert len(candidates) == 4
        assert len(SEEN_THREADS) > 1
        store = get_cache_store()
        for n in range(4):
            assert cache_has(SpyWidget, f"todo-{n}") is True
        assert len(store) == 4


def test_a_workers_non_lookup_error_still_propagates():
    with scope():
        registry.register_instance(SpyWidget.__name__, "a", "resolved-entry")
        with pytest.raises(ValueError, match="loader exploded"):
            walk_manifest([entry("spy_widget", "a", load="boom")], {"todos"})


@pytest.mark.xfail(
    reason="~12% flaky pending #888's freshness-cache race fix; see sub-issue #892",
    strict=False,
)
def test_walk_manifest_stats_shared_template_only_once(monkeypatch):
    """Five dirty candidates over one template file cost one freshness stat.

    Jinja re-asks the loader's `uptodate()` closure on every `get_template()`
    while auto_reload is on, and a fan-out walk looks the same template up once
    per dirty candidate. The request-scoped freshness cache is what keeps that
    from turning into one stat per candidate, including across the build pass's
    threadpool workers.
    """
    shared_template = FanoutWidget.__pjx_descriptor__.template_path
    assert shared_template is not None
    # Both classes render the same file, so the walk has one distinct template
    # path but candidates of two different types resolving to it.
    SpyWidget.__pjx_descriptor__ = dataclasses.replace(
        SpyWidget.__pjx_descriptor__, template_path=shared_template
    )

    original_stat = pathlib.Path.stat

    def counting_stat(self: pathlib.Path, *args: object, **kwargs: object) -> object:
        # The caller's frame name is what separates the freshness re-check from
        # every other stat pathlib makes on the way to loading a template.
        if sys._getframe(1).f_code.co_name == "uptodate":
            STAT_CALLS.append(str(self))
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "stat", counting_stat)

    manifest = [
        entry("fanout_widget", "a", load="todo-1"),
        entry("fanout_widget", "b", load="todo-2"),
        entry("fanout_widget", "c", load="todo-3"),
        entry("spy_widget", "d", load="todo-4"),
        entry("spy_widget", "e", load="todo-5"),
    ]
    with scope():
        candidates = walk_manifest(manifest, {"todos"})

    # Guard against a false pass: the stat count would also be low if the walk
    # had quietly dropped or deduped candidates before rendering them.
    assert [c.instance_id for c in candidates] == ["a", "b", "c", "d", "e"]
    assert sorted(LOAD_CALLS) == ["todo-1", "todo-2", "todo-3"]
    assert len(SEEN_SESSIONS) == 2

    assert STAT_CALLS == [str(shared_template)]
    assert len(STAT_CALLS) != len(candidates)


def test_root_instance_id_reads_a_root_stamped_behind_a_whitespace_prologue():
    """The inverse of stamp_root_attrs must skip the same whitespace segments.

    A level whose root has a whitespace prologue gets its tag stamped into
    segments[1..] by stamp_root_attrs, with root_span rebased absolute past
    the prologue. `_root_instance_id` must walk the same skip to land on the
    same segment, or extraction silently returns None.
    """
    from pyjinhx.root_attrs import stamp_root_attrs

    prologue = "\n  "
    tag = '<div class="root">hi</div>'
    level = RenderedLevel(
        segments=[prologue, tag],
        root_span=(len(prologue), len(prologue) + 18),
        descriptor=None,
    )
    stamp_root_attrs(level, {"data-pjx-id": "abc123"})

    assert fanout._root_instance_id(level) == "abc123"
