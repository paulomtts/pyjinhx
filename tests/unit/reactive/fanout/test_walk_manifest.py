"""Tests for fanout primary-response exclusion, delete/oob swaps and the manifest walk."""

import dataclasses
import re
from typing import Annotated, cast

import pytest

from pyjinhx.components import discovery
from pyjinhx.reactive import fanout
from pyjinhx.reactive.cache import cache_put
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.reactive.fanout import (
    FanoutCandidate,
    _drop_nested,
    _mounted_ids_in,
    delete_swap,
    oob_swaps,
    walk_manifest,
)
from pyjinhx.rendering import registry
from pyjinhx.rendering.session import RenderSession, request_scope
from tests.unit.reactive.fanout._helpers import (
    GONE_KEYS,
    LOAD_CALLS,
    FanoutWidget,
    _entry,
    candidate,
    entry,
    fresh_hash_for,
    scope,
    stamped_level,
)


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

    def spy(candidates, session=None):
        seen_calls.append(len(candidates))
        return original(candidates, session)

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
