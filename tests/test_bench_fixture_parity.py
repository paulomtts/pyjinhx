"""Cheap CI guard: the v0.36 and v2 bench pages must reference the same components.

Not timing-sensitive — no rendering happens here, only manifest comparison,
except for `test_v2_table_cell_content_stays_raw_html` below, which does
render (a single small table) to pin the fixed str-Slot behavior (see
bench_builtin_heavy's module docstring) — #686 restored ADR 0003's
raw-HTML-capable Slot invariant, so this now matches v0's rendering.
"""

import pkgutil

import pyjinhx.builtins
from pyjinhx.component import BaseComponent
from pyjinhx.discovery import build_registry
from pyjinhx.rendering import render as v2_render
from pyjinhx.session import RenderSession
from tests.fixtures.bench_builtin_heavy import (
    V0_MANIFEST,
    V2_MANIFEST,
    build_v0_page,
    build_v2_page,
    build_v2_table,
    component_names,
)


def test_manifests_are_the_same_logical_component_set() -> None:
    assert V0_MANIFEST == V2_MANIFEST


def test_manifest_is_not_trivially_small() -> None:
    # Guards against someone gutting the page to make the bench look good.
    assert len(V0_MANIFEST) >= 20


def test_every_manifest_entry_appears_in_both_page_sources() -> None:
    """Every manifest tag is a substring of v0's markup, and a class in v2's tree.

    v0's page is a flat markup string (its native shape); v2's page is a real
    component instance tree (see bench_builtin_heavy's module docstring for
    why) — so the two sides are checked differently, but assert the same
    thing: every manifest entry is actually present on both sides.
    """
    v0_src = build_v0_page(rows=3)
    v2_names = component_names(build_v2_page(rows=3))
    for logical in V0_MANIFEST:
        assert logical in v0_src, f"{logical} missing from v0 page source"
    for logical in V2_MANIFEST:
        assert logical in v2_names, f"{logical} missing from v2 page tree"


def _v2_registry() -> None:
    """Import every builtin module and register the discovered classes.

    Mirrors scripts/bench_v0_vs_v2.py's `_import_all_v2_builtins` /
    `_v2_all_classes` / `build_registry` sequence — needed here because this
    test actually renders, unlike the manifest-only tests above.
    """
    for module_info in pkgutil.walk_packages(
        pyjinhx.builtins.__path__, prefix="pyjinhx.builtins."
    ):
        __import__(module_info.name)
    found: list[type] = []
    stack = list(BaseComponent.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    build_registry("pyjinhx/builtins", found)


def test_v2_table_cell_content_stays_raw_html() -> None:
    """v2's table cell renders its raw-HTML Slot value raw, matching v0.

    #686 restored ADR 0003's invariant that a plain-`str` Slot value is
    raw-HTML-capable: `_wrap_slot_value` now wraps it in `markupsafe.Markup`
    after retrieval, so pydantic's plain-`str` coercion on assignment (which
    strips `Markup`'s `__html__` protocol) is no longer in the way.
    """
    _v2_registry()
    html = v2_render(build_v2_table(rows=1), RenderSession())
    assert '<input type="text" value="v0"/>' in html
    assert "&lt;input" not in html
