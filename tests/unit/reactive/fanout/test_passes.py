"""Tests for the fanout filter, build and reduce passes and their worker pool."""

import dataclasses
import pathlib
import sys
import threading
import time

import pytest

from pyjinhx.reactive import fanout
from pyjinhx.reactive.cache import cache_has
from pyjinhx.reactive.fanout import FanoutCandidate, walk_manifest
from pyjinhx.reactive.load_cost import note_load_cost
from pyjinhx.rendering import registry
from pyjinhx.rendering.session import RenderSession, get_cache_store, request_scope
from tests.unit.reactive.fanout._helpers import (
    GONE_KEYS,
    LOAD_CALLS,
    SEEN_LOAD_CONTEXTS,
    SEEN_SESSIONS,
    SEEN_THREADS,
    STAT_CALLS,
    FanoutWidget,
    SpyWidget,
    _entry,
    entry,
    scope,
)


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


def test_build_pass_enters_quiet_collisions_once_not_once_per_item(monkeypatch):
    """#1024's fixup: the O(n²) regression was one `quiet_collisions()` call per
    item, each rebuilding a fresh frozenset over the whole pass. Guard the fix
    by pinning the call count to the pass, not the item count."""
    manifest = [_entry(f"row-{i}", "fanout_widget", f"todo-{i}") for i in range(6)]
    calls: list[frozenset] = []
    real_quiet_collisions = registry.quiet_collisions

    def counting_quiet_collisions(keys):
        calls.append(frozenset(keys))
        return real_quiet_collisions(keys)

    monkeypatch.setattr(fanout.registry, "quiet_collisions", counting_quiet_collisions)
    with request_scope() as session:
        items = fanout._filter_pass(manifest, {"todos"}, set())
        fanout._build_pass(items, session)

    assert len(calls) == 1
    assert calls[0] == {registry.make_key("FanoutWidget", f"row-{i}") for i in range(6)}


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
