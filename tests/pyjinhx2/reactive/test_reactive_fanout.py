"""Unit tests for the manifest walk: filter, dedup, and clean/dirty resolution."""

import pytest

from pyjinhx2 import discovery, registry
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
    (tmp_path / "fanout_widget.pjx").write_text("<div>{{ pjx_key }}</div>")
    (tmp_path / "quiet_widget.pjx").write_text("<div>quiet</div>")
    discovery.build_registry(tmp_path, [FanoutWidget, QuietWidget])
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
