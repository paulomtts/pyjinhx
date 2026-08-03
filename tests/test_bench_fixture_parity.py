"""Cheap CI guard: the v0.36 and v2 bench pages must reference the same components.

Not timing-sensitive — no rendering happens here, only manifest comparison,
except for `test_v2_table_cell_content_is_pinned_as_escaped_not_a_bug_to_fix_here`
below, which does render (a single small table) to pin a known, out-of-scope
str-Slot-escaping gap (see bench_builtin_heavy's module docstring) so a
future accidental fix to the renderer doesn't slip by unnoticed here.
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


def test_v2_table_cell_content_is_pinned_as_escaped_not_a_bug_to_fix_here() -> None:
    """v2's table cell renders its raw-HTML Slot value escaped, unlike v0.

    v0's equivalent page (`build_v0_table`) renders a live `<input>` element
    inside this cell; v2 escapes the same markup string to inert text — a
    pre-existing, out-of-scope-for-#537 str-Slot-escaping gap (see
    bench_builtin_heavy's module docstring). Pinned as observed, same as
    `test_a_string_slot_beside_a_component_slot_stays_raw_html` in
    test_slot_semantics_matrix.py, rather than "fixed" here: wrapping the
    value in `markupsafe.Markup` does not survive pydantic's plain-`str`
    coercion on the Slot field, so there is no fixture-only fix available.
    """
    _v2_registry()
    html = v2_render(build_v2_table(rows=1), RenderSession(template_dir="/"))
    assert "&lt;input" in html
    assert '<input type="text" value="v0"/>' not in html
