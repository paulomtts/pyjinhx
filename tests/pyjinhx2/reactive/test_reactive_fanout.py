"""Unit tests for the manifest walk: filter, dedup, and clean/dirty resolution."""

import dataclasses
import re
from pathlib import Path
from typing import Annotated

import pytest

from pyjinhx2 import discovery, registry
from pyjinhx2.component import BaseComponent
from pyjinhx2.reactive import fanout
from pyjinhx2.reactive.cache import cache_has, cache_put
from pyjinhx2.reactive.component import PjxKey, ReactiveComponent
from pyjinhx2.reactive.fanout import (
    FanoutCandidate,
    _drop_nested,
    _mounted_ids_in,
    delete_swap,
    oob_swaps,
    walk_manifest,
)
from pyjinhx2.segments import ChildRef, RenderedLevel
from pyjinhx2.session import RenderSession, request_scope

LOAD_CALLS: list[str | None] = []


class FanoutWidget(ReactiveComponent, react=("todos",)):
    """A reactive component keyed by ``pjx_key``, whose load() is counted."""

    pjx_key: Annotated[str, PjxKey()] = ""

    def load(self) -> str:
        LOAD_CALLS.append(self.pjx_key)
        return f"data:{self.pjx_key}"


class QuietWidget(ReactiveComponent, react=("other",)):
    """A reactive component that no test's dirtied keys ever touch."""


class PlainWidget(BaseComponent):
    """A discovery-registered component that is NOT a ReactiveComponent.

    A manifest naming a real tag whose class is non-reactive must be dropped by
    the `issubclass` half of `_candidate_class`, not by the unknown-tag half.
    """


_TEMPLATE_DIR = "templates"
"""Set by `_clean_registries` to this test's tmp_path. `RenderSession(template_dir="templates")`
(the class default) does not exist relative to the test's cwd — every test must enter
`scope()`, never bare `request_scope()`, or the dirty path's `render_level()` call raises
`TemplateNotFound` instead of exercising the code under test."""


@pytest.fixture(autouse=True)
def _clean_registries(tmp_path, monkeypatch):
    """Publish a tag -> class map for the two test classes and reset call spies."""
    global _TEMPLATE_DIR
    LOAD_CALLS.clear()
    fanout_path = tmp_path / "fanout_widget.pjx"
    quiet_path = tmp_path / "quiet_widget.pjx"
    fanout_path.write_text("<div>{{ pjx_key }}</div>")
    quiet_path.write_text("<div>quiet</div>")
    plain_path = tmp_path / "plain_widget.pjx"
    plain_path.write_text("<div>plain</div>")
    discovery.build_registry(tmp_path, [FanoutWidget, QuietWidget, PlainWidget])
    PlainWidget.__pjx_descriptor__ = dataclasses.replace(
        PlainWidget.__pjx_descriptor__, template_path=Path(plain_path.name)
    )
    # `_resolve_template_path` walks the class's *defining module's* directory
    # (this test file's dir), not `template_dir` passed to `build_registry` —
    # the two are deliberately different concerns (tag lookup vs. file probe).
    # Point each descriptor's `template_path` at this test's tmp_path file, the
    # same way tests/pyjinhx2/test_render_integration.py does, so render_level()
    # finds a real file instead of falling back to an ancestor's unprobed guess.
    # `RenderSession(template_dir=tmp_path)` (below, via `scope()`) resolves a
    # template name relative to that dir, so the descriptor's `template_path`
    # must be the bare filename, not `fanout_path` itself (an absolute path
    # jinja's FileSystemLoader would join *under* the search dir, not open
    # directly, and never find).
    FanoutWidget.__pjx_descriptor__ = dataclasses.replace(
        FanoutWidget.__pjx_descriptor__, template_path=Path(fanout_path.name)
    )
    QuietWidget.__pjx_descriptor__ = dataclasses.replace(
        QuietWidget.__pjx_descriptor__, template_path=Path(quiet_path.name)
    )
    _TEMPLATE_DIR = str(tmp_path)
    yield


def entry(
    type_name: str, instance_id: str, load: object = None, hash_: str = "h"
) -> dict:
    """Build one synthetic X-PJX-Mounted manifest entry."""
    return {"type": type_name, "id": instance_id, "load": load, "hash": hash_}


def scope():
    """`request_scope()` bound to this test's tmp_path template dir.

    Bare `request_scope()` defaults `template_dir` to the literal string
    `"templates"`, which does not exist relative to the test process's cwd —
    every test must go through this helper, never call `request_scope()`
    directly, or a dirty-path `render_level()` call fails to find the
    fixture's `.pjx` file instead of exercising the code under test.
    """
    return request_scope(_TEMPLATE_DIR)


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
        [candidate] = walk_manifest([entry("fanout_widget", "a")], {"todos"})
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
        assert cache_has(FanoutWidget, "todo-1") is True
        assert candidate.level is not None
        assert isinstance(candidate.level, RenderedLevel)
        assert candidate.level.root_span is not None
        assert candidate.instance is not None


def test_unregistered_entry_is_a_miss_and_does_not_abort_the_walk():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "b", "resolved-entry")
        manifest = [
            entry("fanout_widget", "gone", load="todo-1"),
            entry("fanout_widget", "b", load="todo-2"),
        ]
        gone, alive = walk_manifest(manifest, {"todos"})
        assert gone.status == "missing"
        assert gone.resolved is None
        assert alive.status == "dirty"


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
            "pyjinhx2.reactive.fanout.registry.register_instance",
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
    return FanoutWidget(id="probe", pjx_key=str(load)).state_hash()


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
    with scope():
        # Nothing registered under this id, so registry.resolve() raises and the
        # entry is "missing" — #470's delete-swap input, which this gate must
        # not consume even when the reported hash is the matching one.
        manifest = [
            entry(
                "fanout_widget", "gone", load="todo-1", hash_=fresh_hash_for("todo-1")
            )
        ]
        [candidate] = walk_manifest(manifest, {"todos"})
        assert candidate.status == "missing"
        assert candidate.fresh_hash is None


def test_mixed_manifest_gates_only_the_dirty_entries():
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        registry.register_instance(FanoutWidget.__name__, "a", "level-a")
        registry.register_instance(FanoutWidget.__name__, "same", "level-same")
        registry.register_instance(FanoutWidget.__name__, "moved", "level-moved")
        manifest = [
            # clean: cached, reports the hash its own fresh render would have
            entry("fanout_widget", "a", load="todo-1", hash_=fresh_hash_for("todo-1")),
            # dirty + gated out: fresh hash equals the reported one
            entry(
                "fanout_widget", "same", load="todo-2", hash_=fresh_hash_for("todo-2")
            ),
            # dirty + survives: reported hash is stale
            entry("fanout_widget", "moved", load="todo-3", hash_="stale"),
            # missing: never resolved, gate must not touch it
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
        # a guess about the data. The "gone" entry never loads: in
        # `walk_manifest`, `_resolve_registry_entry`'s LookupError sets
        # status="missing" before `_build_dirty` (and therefore `load()`) is
        # ever reached, so only the two dirty entries appear here.
        assert LOAD_CALLS == ["todo-2", "todo-3"]


def test_mixed_manifest_produces_the_expected_ordered_candidate_list():
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        registry.register_instance(FanoutWidget.__name__, "a", "level-a")
        registry.register_instance(FanoutWidget.__name__, "c", "level-c")
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
        # Only the dirty candidate ran its body; the clean one was never loaded
        # and the missing one was never built.
        assert LOAD_CALLS == ["todo-2"]


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
    assert candidate_.status == "missing"
    assert LOAD_CALLS == []


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
    assert omitted == explicit_none == [("a", "missing"), ("b", "missing")]


def test_primary_exclusion_and_nesting_dedup_compose_in_one_walk(monkeypatch):
    """One entry dropped by the primary, a separate pair still deduped by nesting."""
    child = stamped_level("child")
    parent = stamped_level("parent", child)
    levels = {"parent": parent, "child": child}

    def fake_build_dirty(cls, instance_id, load, session):
        return cls(id=instance_id), levels[instance_id]

    monkeypatch.setattr("pyjinhx2.reactive.fanout._build_dirty", fake_build_dirty)
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
    with scope():
        [candidate_] = walk_manifest(
            [entry("fanout_widget", "gone-1", load="todo-1")], {"todos"}
        )
    assert candidate_.status == "missing"
    assert (
        delete_swap(candidate_)
        == "<div hx-swap-oob=\"delete:[data-pjx-id='gone-1']\"></div>"
    )
    # A missing region costs no load, no render and no registry write on the
    # whole path from manifest entry to delete fragment.
    assert LOAD_CALLS == []
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

    monkeypatch.setattr("pyjinhx2.reactive.fanout._drop_nested", spy)
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
    # session, no scope" path literally. Instead: a *bogus* ambient scope
    # (bare `request_scope()` defaults `template_dir="templates"`, which does
    # not exist relative to the test process's cwd) proves the explicit
    # `session=` argument is actually taken and not merely tolerated alongside
    # a correct ambient one — if it were ignored in favor of
    # `current_session()`, this would raise `TemplateNotFound`.
    with request_scope():
        registry.register_instance(FanoutWidget.__name__, "s", "entry-s")
        [explicit] = walk_manifest(
            manifest, {"todos"}, session=RenderSession(template_dir=_TEMPLATE_DIR)
        )

    assert ambient.status == explicit.status == "dirty"
    assert ambient.fresh_hash == explicit.fresh_hash == fresh_hash_for("todo-1")
