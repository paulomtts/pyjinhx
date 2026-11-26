"""Tests for fanout nested-root registration quieting and deferred nested candidates."""

import dataclasses
import logging
import re

import pytest

from pyjinhx import dev
from pyjinhx.reactive import fanout
from pyjinhx.reactive.cache import cache_put
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.reactive.fanout import oob_swaps, walk_manifest
from pyjinhx.reactive.load_cost import note_load_cost
from pyjinhx.reactive.root_attrs import record_nested_react_keys
from pyjinhx.rendering import registry
from pyjinhx.rendering.registry import InstanceKeyCollisionError
from pyjinhx.rendering.segments import RenderedLevel
from pyjinhx.rendering.session import get_quiet_collisions, request_scope
from tests.unit.reactive.fanout._helpers import (
    BOOM_KEYS,
    GONE_KEYS,
    LOAD_CALLS,
    RENDERS,
    FanoutWidget,
    HostWidget,
    MiddleWidget,
    NestedChildWidget,
    NestingParentWidget,
    counting_session,
    entry,
    scope,
    swaps,
    wired_session,
)


def host_hash(cls: type[ReactiveComponent], load: str) -> str:
    """The state hash the walk will compute for this gate-free class and load key.

    The `fresh_hash_for` idea, for classes whose only field is `pjx_key`, so a
    test can seed a manifest hash that makes the hash gate drop the region.
    """
    return cls(id="probe", pjx_key=load).state_hash()


@pytest.fixture
def strict_dev():
    """Reactive-dev strict mode on for one test, off again afterwards.

    Process-wide, not request-scoped, so leaving it on would leak into every
    test that runs after this one.
    """
    dev.enable_reactive_dev(strict=True)
    yield
    dev.disable_reactive_dev()


def nesting_manifest() -> list[dict]:
    """The #1022 manifest: the nested child first, then its containing parent.

    Child first is deliberate. The child's own dedicated build registers
    `NestedChildWidget_child-1`; the parent's build then re-renders the same
    region as a nested descendant and writes that key a second time. That second
    write is the one this subtask quiets.
    """
    return [
        entry("nested_child_widget", "child-1", load="k1"),
        entry("nesting_parent_widget", "parent-1", load="k1"),
    ]


# --- Deferred nested candidates: the manifest's `parent` hint ---------------


def host_entry(hash_: str = "stale", **kwargs: object) -> dict:
    """The default parent-first manifest's HostWidget entry, `host-1` at `k1`."""
    return entry("host_widget", "host-1", load="k1", hash_=hash_, **kwargs)


def child_entry(
    load: str = "k1", instance_id: str = "child-1", **kwargs: object
) -> dict:
    """A NestedChildWidget entry, `child-1` at `k1` unless told otherwise."""
    return entry("nested_child_widget", instance_id, load=load, hash_="stale", **kwargs)


def without_parent(manifest: list[dict]) -> list[dict]:
    """The same manifest as an old client would send it: no entry carries `parent`."""
    return [
        {key: value for key, value in e.items() if key != "parent"} for e in manifest
    ]


def survivor_ids(shapes: list[tuple]) -> list[str]:
    """The instance ids out of `swaps()`'s candidate shapes, in order."""
    return [shape[0] for shape in shapes]


@dataclasses.dataclass
class Comparison:
    """A with-`parent` walk, its no-`parent` baseline, and the hinted walk's spies."""

    hinted: tuple[str, list[tuple]]
    baseline: tuple[str, list[tuple]]
    loads: list[str]
    renders: list[str]
    baseline_renders: list[str]


def compare(manifest, primary_html=None, before=None) -> Comparison:
    """Walk `manifest` as sent, then again with every `parent` removed.

    The spies are cleared before each walk, so `loads` and `renders` count
    the with-`parent` walk alone and `baseline_renders` the baseline alone.
    """
    LOAD_CALLS.clear()
    RENDERS.clear()
    hinted = swaps(manifest, primary_html, before)
    loads, renders = list(LOAD_CALLS), list(RENDERS)
    LOAD_CALLS.clear()
    RENDERS.clear()
    baseline = swaps(without_parent(manifest), primary_html, before)
    return Comparison(hinted, baseline, loads, renders, list(RENDERS))


def chain_manifest() -> list[dict]:
    """Outer > Middle > child, all dirty, each naming its nearest mounted ancestor."""
    return [
        entry("outer_widget", "outer-1", load="k1", hash_="stale"),
        entry("middle_widget", "middle-1", load="k1", hash_="stale", parent="outer-1"),
        child_entry(parent="middle-1"),
    ]


def tag_with_id(body: str, instance_id: str) -> str:
    """The opening tag carrying this `data-pjx-id`, wherever the attr sits in it."""
    match = re.search(rf'<[^<>]*data-pjx-id="{re.escape(instance_id)}"[^<>]*>', body)
    assert match is not None, f"no tag carries data-pjx-id={instance_id!r}"
    return match.group(0)


def test_root_instance_id_reads_a_root_stamped_behind_a_whitespace_prologue():
    """The inverse of stamp_root_attrs must skip the same whitespace segments.

    A level whose root has a whitespace prologue gets its tag stamped into
    segments[1..] by stamp_root_attrs, with root_span rebased absolute past
    the prologue. `_root_instance_id` must walk the same skip to land on the
    same segment, or extraction silently returns None.
    """
    from pyjinhx.rendering.root_attrs import stamp_root_attrs

    prologue = "\n  "
    tag = '<div class="root">hi</div>'
    level = RenderedLevel(
        segments=[prologue, tag],
        root_span=(len(prologue), len(prologue) + 18),
        descriptor=None,
    )
    stamp_root_attrs(level, {"data-pjx-id": "abc123"})

    assert fanout._root_instance_id(level) == "abc123"


def test_walk_manifest_wires_the_nested_react_key_recorder_exactly_once():
    """The subscriber is appended per walk, guarded the way responses.py guards its own."""
    with scope() as session:
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        walk_manifest(
            [entry("fanout_widget", "a", load="todo-1")], {"todos"}, session=session
        )
        walk_manifest(
            [entry("fanout_widget", "a", load="todo-2")], {"todos"}, session=session
        )
    assert session.on_rendered.count(record_nested_react_keys) == 1
    assert session.nested_react_keys["a"] == ("todos",)


def test_a_nested_child_that_is_also_its_own_candidate_registers_silently(caplog):
    """The old-client path: a manifest with no `parent` builds both regions.

    With no hint to defer on, the child's own build and the parent's nested
    render of it both run, as they always have, and the second registry write
    of the child's key stays quiet.
    """
    session = wired_session()
    with (
        request_scope(session=session),
        caplog.at_level(logging.WARNING, logger="pyjinhx"),
    ):
        walk_manifest(nesting_manifest(), {"todos"})

    assert [record.getMessage() for record in caplog.records] == []
    # Both builds really ran — the quieting is about the noise, not about
    # skipping the redundant work (an explicit Non-goal).
    assert "child:k1" in LOAD_CALLS
    assert "parent:k1" in LOAD_CALLS


def test_the_nested_double_registration_does_not_crash_dev_strict(strict_dev):
    """Today's false positive: dev-strict turns the benign shape into a 500."""
    session = wired_session()
    with request_scope(session=session):
        candidates = walk_manifest(nesting_manifest(), {"todos"})

    assert [candidate.instance_id for candidate in candidates] == ["parent-1"]


def test_the_nesting_dedup_output_is_unchanged_by_the_quieting():
    """Non-goal guard: which swap ships is still _drop_nested's call, unchanged."""
    session = wired_session()
    with request_scope(session=session):
        candidates = walk_manifest(nesting_manifest(), {"todos"})
        body = oob_swaps(candidates)

    assert [(c.instance_id, c.status) for c in candidates] == [("parent-1", "dirty")]
    swaps = re.findall(r'hx-swap-oob="([^:]+):\[data-pjx-id=\'([^\']+)\'', body)
    assert swaps == [("outerHTML", "parent-1")]


def test_two_unrelated_candidates_sharing_one_id_still_warn(caplog):
    """The authoring bug is not masked: neither region is nested in the other."""
    session = wired_session()
    manifest = [
        entry("fanout_widget", "shared", load="todo-1"),
        entry("fanout_widget", "shared", load="todo-2"),
    ]
    with (
        request_scope(session=session),
        caplog.at_level(logging.WARNING, logger="pyjinhx"),
    ):
        walk_manifest(manifest, {"todos"})

    messages = [record.getMessage() for record in caplog.records]
    assert [m for m in messages if "FanoutWidget_shared" in m and "overwriting" in m]


def test_two_unrelated_candidates_sharing_one_id_still_raise_under_strict(strict_dev):
    """Same shape, dev-strict: the raise still travels out of the build pass."""
    session = wired_session()
    manifest = [
        entry("fanout_widget", "shared", load="todo-1"),
        entry("fanout_widget", "shared", load="todo-2"),
    ]
    with (
        request_scope(session=session),
        pytest.raises(InstanceKeyCollisionError, match="FanoutWidget_shared"),
    ):
        walk_manifest(manifest, {"todos"})


def test_the_quieting_holds_on_the_inline_build_branch(caplog):
    """The all-cheap branch runs on the caller's own ContextVars, not a copy."""
    note_load_cost(NestedChildWidget, 0.0)
    note_load_cost(NestingParentWidget, 0.0)

    def no_pool(*args, **kwargs):
        raise AssertionError("the too-cheap path must not build a ThreadPoolExecutor")

    session = wired_session()
    with (
        request_scope(session=session),
        pytest.MonkeyPatch.context() as patch,
        caplog.at_level(logging.WARNING, logger="pyjinhx"),
    ):
        patch.setattr(fanout, "ThreadPoolExecutor", no_pool)
        candidates = walk_manifest(nesting_manifest(), {"todos"})

    assert [record.getMessage() for record in caplog.records] == []
    assert [candidate.instance_id for candidate in candidates] == ["parent-1"]
    # And the block left nothing behind on the caller's own context.
    assert get_quiet_collisions() == frozenset()


def test_a_nested_candidate_with_a_dirty_parent_is_not_built():
    run = compare([host_entry(), child_entry(parent="host-1")])

    assert run.loads.count("child:k1") == 1
    # Only the copy rendered inside the host: the child's own build never ran.
    assert run.renders.count("NestedChildWidget") == 1
    assert survivor_ids(run.hinted[1]) == ["host-1"]
    assert run.hinted == run.baseline


def test_an_empty_wave_two_builds_nothing_more(monkeypatch):
    built: list[str] = []
    real_build_one = fanout._build_one

    def counting_build_one(item, session):
        built.append(item.instance_id)
        return real_build_one(item, session)

    quiet_calls: list[frozenset] = []
    real_quiet_collisions = registry.quiet_collisions

    def counting_quiet_collisions(keys):
        quiet_calls.append(frozenset(keys))
        return real_quiet_collisions(keys)

    monkeypatch.setattr(fanout, "_build_one", counting_build_one)
    monkeypatch.setattr(fanout.registry, "quiet_collisions", counting_quiet_collisions)
    swaps([host_entry(), child_entry(parent="host-1")])

    assert built == ["host-1"]
    assert quiet_calls == [
        {
            registry.make_key("HostWidget", "host-1"),
            registry.make_key("NestedChildWidget", "child-1"),
        }
    ]


def test_a_different_load_key_in_the_parent_still_wins():
    run = compare([host_entry(), child_entry(load="k9", parent="host-1")])

    assert "child:k9" not in run.loads
    assert survivor_ids(run.hinted[1]) == ["host-1"]
    assert "child k1" in run.hinted[0]
    assert run.hinted == run.baseline


@pytest.mark.parametrize(
    ("prefix", "primary_html"),
    [
        pytest.param([entry("no_such_widget", "p-1")], None, id="unknown_tag"),
        pytest.param([entry("quiet_widget", "p-1")], None, id="keys_not_dirtied"),
        pytest.param(
            [entry("host_widget", "p-1", load="k1", hash_="stale")],
            '<div data-pjx-id="p-1"></div>',
            id="excluded_by_primary",
        ),
        pytest.param(
            [
                entry("fanout_widget", "a", load="x", hash_="stale"),
                entry("fanout_widget", "p-1", load="x", hash_="stale"),
            ],
            None,
            id="dedup_dropped",
        ),
    ],
)
def test_a_child_whose_parent_is_not_a_surviving_candidate_is_built(
    prefix, primary_html
):
    run = compare([*prefix, child_entry(parent="p-1")], primary_html=primary_html)

    assert "child:k1" in run.loads
    assert "child-1" in survivor_ids(run.hinted[1])
    assert run.hinted == run.baseline


def test_a_child_whose_parent_is_clean_is_built():
    def seed():
        cache_put(HostWidget, "k1", HostWidget(pjx_key="k1"), react_keys=("todos",))

    run = compare([host_entry(), child_entry(parent="host-1")], before=seed)

    statuses = {shape[0]: shape[1] for shape in run.hinted[1]}
    assert statuses == {"host-1": "clean", "child-1": "dirty"}
    assert "child:k1" in run.loads
    assert run.hinted == run.baseline


def test_a_child_whose_parent_is_hash_gated_is_built_in_wave_two_and_ships_alone():
    # Output only: see the spec's Known limitation on this path's registry log.
    manifest = [
        host_entry(hash_=host_hash(HostWidget, "k1")),
        child_entry(parent="host-1"),
    ]
    run = compare(manifest)

    assert [(s[0], s[1]) for s in run.hinted[1]] == [("child-1", "dirty")]
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='child-1']\"" in run.hinted[0]
    # Once nested in the gated host, once as its own wave-two build.
    assert run.renders.count("NestedChildWidget") == 2
    assert run.hinted == run.baseline


def test_a_child_whose_parent_is_missing_is_built_in_wave_two():
    GONE_KEYS.add("k1")
    run = compare([host_entry(), child_entry(parent="host-1")])

    assert [(s[0], s[1]) for s in run.hinted[1]] == [
        ("host-1", "missing"),
        ("child-1", "dirty"),
    ]
    assert "<div hx-swap-oob=\"delete:[data-pjx-id='host-1']\"></div>" in run.hinted[0]
    assert "child:k1" in run.loads
    assert run.hinted == run.baseline


def test_a_lying_parent_claim_falls_back_to_a_build():
    manifest = [
        entry("hollow_host_widget", "hollow-1", load="k1", hash_="stale"),
        child_entry(parent="hollow-1"),
    ]
    run = compare(manifest)

    assert survivor_ids(run.hinted[1]) == ["hollow-1", "child-1"]
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='hollow-1']\"" in run.hinted[0]
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='child-1']\"" in run.hinted[0]
    assert "child:k1" in run.loads
    assert run.renders.count("NestedChildWidget") == 1
    assert run.hinted == run.baseline


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param([host_entry(), child_entry(parent="child-1")], id="self"),
        pytest.param([host_entry(), child_entry(parent="nobody")], id="unknown"),
        pytest.param([child_entry(parent="host-1"), host_entry()], id="forward"),
        pytest.param([host_entry(), child_entry(parent=None)], id="none"),
        pytest.param([host_entry(), child_entry(parent="")], id="empty"),
        pytest.param([host_entry(), child_entry(parent=7)], id="int"),
        pytest.param([host_entry(), child_entry(parent=["host-1"])], id="list"),
        pytest.param([host_entry(), child_entry(parent={"id": "host-1"})], id="dict"),
        pytest.param([host_entry(), child_entry(parent=True)], id="bool"),
    ],
)
def test_parent_self_unknown_forward_and_non_string_are_ignored(manifest):
    run = compare(manifest)

    assert run.loads.count("child:k1") >= 1
    # The child's own build ran beside the host's nested render of it.
    assert run.renders.count("NestedChildWidget") == 2
    assert run.renders.count("NestedChildWidget") == run.baseline_renders.count(
        "NestedChildWidget"
    )
    assert run.hinted == run.baseline


def test_a_deferred_child_that_is_gone_becomes_a_delete_swap():
    GONE_KEYS.add("gone")
    manifest = [
        entry("hollow_host_widget", "hollow-1", load="k1", hash_="stale"),
        entry("host_widget", "host-9", load="gone", hash_="stale", parent="hollow-1"),
    ]
    run = compare(manifest)

    assert [(s[0], s[1]) for s in run.hinted[1]] == [
        ("hollow-1", "dirty"),
        ("host-9", "missing"),
    ]
    assert "<div hx-swap-oob=\"delete:[data-pjx-id='host-9']\"></div>" in run.hinted[0]
    assert run.hinted == run.baseline


def test_a_deferred_child_with_an_empty_id_is_never_proven():
    run = compare([host_entry(), child_entry(instance_id="", parent="host-1")])

    assert survivor_ids(run.hinted[1]) == ["host-1", ""]
    assert run.renders.count("NestedChildWidget") == 2
    assert run.hinted == run.baseline


def test_a_clean_child_with_a_parent_is_never_deferred():
    def seed():
        cache_put(
            NestedChildWidget,
            "k1",
            NestedChildWidget(pjx_key="k1"),
            react_keys=("todos",),
        )

    run = compare([host_entry(), child_entry(parent="host-1")], before=seed)

    assert survivor_ids(run.hinted[1]) == ["host-1"]
    assert "child:k1" not in run.loads
    assert run.renders.count("NestedChildWidget") == 1
    assert run.hinted == run.baseline


def test_a_three_level_chain_defers_both_descendants():
    run = compare(chain_manifest())

    assert run.loads.count("outer:k1") == 1
    assert run.loads.count("middle:k1") == 1
    assert run.loads.count("child:k1") == 1
    assert run.renders.count("OuterWidget") == 1
    assert run.renders.count("MiddleWidget") == 1
    assert run.renders.count("NestedChildWidget") == 1
    assert survivor_ids(run.hinted[1]) == ["outer-1"]
    assert run.hinted == run.baseline


def test_a_dirty_grandchild_under_a_clean_middle_is_built_as_a_root():
    def seed():
        cache_put(MiddleWidget, "k1", MiddleWidget(pjx_key="k1"), react_keys=("todos",))

    run = compare(chain_manifest(), before=seed)

    # Nearest ancestor only: the clean middle leaves the child a root, so its
    # standalone build runs beside the copy nested in outer > middle.
    assert run.renders.count("NestedChildWidget") == 2
    assert survivor_ids(run.hinted[1]) == ["outer-1"]
    assert run.hinted == run.baseline


def test_wave_two_runs_under_the_same_quieting(strict_dev, caplog, monkeypatch):
    manifest = [
        entry("hollow_host_widget", "hollow-1", load="k1", hash_="stale"),
        child_entry(parent="hollow-1"),
        entry("fanout_widget", "f-1", load="f", hash_="stale"),
    ]
    pass_keys = {
        registry.make_key("HollowHostWidget", "hollow-1"),
        registry.make_key("NestedChildWidget", "child-1"),
        registry.make_key("FanoutWidget", "f-1"),
    }
    quiet_calls: list[frozenset] = []
    real_quiet_collisions = registry.quiet_collisions

    def counting_quiet_collisions(keys):
        quiet_calls.append(frozenset(keys))
        return real_quiet_collisions(keys)

    seen_quiet: dict[str, frozenset] = {}
    real_build_one = fanout._build_one

    def recording_build_one(item, session):
        seen_quiet[item.instance_id] = get_quiet_collisions()
        return real_build_one(item, session)

    monkeypatch.setattr(fanout.registry, "quiet_collisions", counting_quiet_collisions)
    monkeypatch.setattr(fanout, "_build_one", recording_build_one)
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        _, shapes = swaps(manifest)

    assert survivor_ids(shapes) == ["hollow-1", "child-1", "f-1"]
    # One quiet block per wave, both over the whole filtered list.
    assert quiet_calls == [pass_keys, pass_keys]
    assert seen_quiet == {
        "hollow-1": pass_keys,
        "f-1": pass_keys,
        "child-1": pass_keys,
    }
    assert not [r for r in caplog.records if "already registered" in r.getMessage()]
    assert get_quiet_collisions() == frozenset()


def test_a_deferred_item_never_reaches_preserve_stamping():
    manifest = [
        entry("preserving_host_widget", "phost-1", load="k1", hash_="stale"),
        child_entry(parent="phost-1"),
    ]
    run = compare(manifest)

    assert survivor_ids(run.hinted[1]) == ["phost-1"]
    assert run.renders.count("NestedChildWidget") == 1
    body = run.hinted[0]
    assert 'hx-preserve="true"' in tag_with_id(body, "quiet-1")
    assert "hx-preserve" not in tag_with_id(body, "child-1")
    assert run.hinted == run.baseline


@pytest.mark.parametrize("branch", ["inline", "threaded"])
def test_the_deferral_holds_on_both_build_branches(branch):
    pools: list[int] = []
    real_pool = fanout.ThreadPoolExecutor

    def counting_pool(*args, **kwargs):
        pools.append(1)
        return real_pool(*args, **kwargs)

    def no_pool(*args, **kwargs):
        raise AssertionError("the too-cheap path must not build a ThreadPoolExecutor")

    if branch == "inline":
        note_load_cost(HostWidget, 0.0)
        note_load_cost(NestedChildWidget, 0.0)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            fanout,
            "ThreadPoolExecutor",
            no_pool if branch == "inline" else counting_pool,
        )
        _, shapes = swaps([host_entry(), child_entry(parent="host-1")])

    assert LOAD_CALLS.count("child:k1") == 1
    assert RENDERS.count("NestedChildWidget") == 1
    assert survivor_ids(shapes) == ["host-1"]
    assert pools == ([] if branch == "inline" else [1])


def test_a_raise_in_wave_one_never_starts_wave_two():
    BOOM_KEYS.add("k1")
    with (
        request_scope(session=counting_session()),
        pytest.raises(ValueError, match="host loader exploded"),
    ):
        walk_manifest([host_entry(), child_entry(parent="host-1")], {"todos"})

    assert "child:k1" not in LOAD_CALLS
    assert RENDERS.count("NestedChildWidget") == 0


def test_one_walk_drops_the_proven_child_and_builds_the_unproven_one():
    manifest = [
        host_entry(),
        child_entry(parent="host-1"),
        entry("hollow_host_widget", "hollow-1", load="k1", hash_="stale"),
        entry("fanout_widget", "f-1", load="f", hash_="stale", parent="hollow-1"),
    ]
    run = compare(manifest)

    assert survivor_ids(run.hinted[1]) == ["host-1", "hollow-1", "f-1"]
    assert run.renders.count("NestedChildWidget") == 1
    assert "f" in run.loads
    assert run.hinted == run.baseline
