"""Tests for fanout candidate selection, hash gating, nesting drops and preserve stamping."""

import dataclasses

from pyjinhx.components import discovery
from pyjinhx.reactive import fanout
from pyjinhx.reactive.cache import cache_has, cache_put
from pyjinhx.reactive.fanout import (
    FanoutCandidate,
    _drop_nested,
    oob_swaps,
    walk_manifest,
)
from pyjinhx.rendering import registry
from pyjinhx.rendering.segments import ChildRef, RenderedLevel
from tests.unit.reactive.fanout._helpers import (
    GONE_KEYS,
    LOAD_CALLS,
    FanoutWidget,
    PlainWidget,
    QuietWidget,
    candidate,
    entry,
    fresh_hash_for,
    scope,
    stamped_level,
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


def nested_tag_of(body: str, instance_id: str) -> str:
    """The opening tag of the nested root with this id, out of a serialized body."""
    start = body.index(f'<div data-pjx-id="{instance_id}"')
    return body[start : body.index(">", start) + 1]


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
    """The single-candidate short-circuit walks nothing (#1028): a lone
    candidate might be clean or missing, never reaching `_preserve_nested`, so
    populating its `nested_roots` cache here would risk pure waste. The
    returned candidate is the exact original object, unlike the >=2 branch."""
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

    def counting_contained(level, session=None):
        calls.append(id(level))
        return real_contained(level, session)

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
