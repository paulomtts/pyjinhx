"""Unit tests for the manifest walk: filter, dedup, and clean/dirty resolution."""

import dataclasses
from pathlib import Path

import pytest

from pyjinhx2 import discovery, registry
from pyjinhx2.reactive.cache import cache_has, cache_put
from pyjinhx2.reactive.component import PjxKey, ReactiveComponent
from pyjinhx2.reactive.fanout import walk_manifest
from pyjinhx2.session import RenderSession, request_scope

from typing import Annotated


LOAD_CALLS: list[str | None] = []


class FanoutWidget(ReactiveComponent, react=("todos",)):
    """A reactive component keyed by ``pjx_key``, whose load() is counted."""

    pjx_key: Annotated[str, PjxKey()] = ""

    def load(self) -> str:
        LOAD_CALLS.append(self.pjx_key)
        return f"data:{self.pjx_key}"


class QuietWidget(ReactiveComponent, react=("other",)):
    """A reactive component that no test's dirtied keys ever touch."""


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
    discovery.build_registry(tmp_path, [FanoutWidget, QuietWidget])
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


def entry(type_name: str, instance_id: str, load: object = None, hash_: str = "h") -> dict:
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


def test_cache_hit_answers_clean_without_calling_load():
    with scope():
        cache_put(FanoutWidget, "todo-1", "cached-payload", react_keys=("todos",))
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        [candidate] = walk_manifest([entry("fanout_widget", "a", load="todo-1")], {"todos"})
        assert candidate.status == "clean"
        assert candidate.resolved == "resolved-entry"
        assert candidate.level is None
        assert LOAD_CALLS == []


def test_cache_miss_loads_once_renders_and_caches():
    with scope():
        registry.register_instance(FanoutWidget.__name__, "a", "resolved-entry")
        [candidate] = walk_manifest([entry("fanout_widget", "a", load="todo-1")], {"todos"})
        assert candidate.status == "dirty"
        assert LOAD_CALLS == ["todo-1"]
        assert cache_has(FanoutWidget, "todo-1") is True
        assert candidate.level is not None
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
