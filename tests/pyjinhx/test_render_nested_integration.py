"""End-to-end integration tests for the ChildRef fill across nested trees.

Composes resolve + instantiate + recurse + splice on deeper, mixed and
loop-generated trees than the per-feature files cover. Tests only: no
production code change was needed to make them pass.
"""

from pathlib import Path

import pytest
from pydantic import Field

from pyjinhx import discovery
from pyjinhx._component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render, render_level
from pyjinhx.segments import ChildRef, RenderedLevel, serialize
from pyjinhx.session import RenderSession

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def descriptor_for(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    """Attach a minimal descriptor pointing at a fixture template."""
    return ClassDescriptor(
        template_path=_TEMPLATE_DIR / template,
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


class PJXNestedLeaf(BaseComponent):
    label: str = ""


PJXNestedLeaf.__pjx_descriptor__ = descriptor_for(PJXNestedLeaf, "nested_leaf.html")


class PJXNestedMid(BaseComponent):
    label: str = ""


PJXNestedMid.__pjx_descriptor__ = descriptor_for(PJXNestedMid, "nested_mid.html")


class PJXNestedRoot(BaseComponent):
    pass


PJXNestedRoot.__pjx_descriptor__ = descriptor_for(PJXNestedRoot, "nested_root.html")


@pytest.fixture(autouse=True)
def registry():
    """Each test starts from a mapping holding just the fixture components."""
    discovery._registry.mapping = {
        "pjx_nested_leaf": PJXNestedLeaf,
        "pjx_nested_mid": PJXNestedMid,
        "pjx_mixed_mid": PJXMixedMid,
        "pjx_full_mid": PJXFullMid,
    }
    yield
    discovery._registry.mapping = {}


@pytest.fixture
def session():
    return RenderSession()


def test_three_levels_nest_as_rendered_levels(session):
    level = render_level(PJXNestedRoot(), session)
    mid = level.segments[1]
    assert isinstance(mid, RenderedLevel)
    assert mid.descriptor is PJXNestedMid.__pjx_descriptor__
    leaf = mid.segments[2]
    assert isinstance(leaf, RenderedLevel)
    assert leaf.descriptor is PJXNestedLeaf.__pjx_descriptor__


def test_three_levels_serialize_nested_in_order(session):
    assert render(PJXNestedRoot(), session) == (
        '<div class="root"><span class="mid">m<em class="leaf">deep</em></span></div>'
    )


def test_no_childref_survives_the_fill_at_any_depth(session):
    level = render_level(PJXNestedRoot(), session)

    def walk(node: RenderedLevel) -> None:
        for seg in node.segments:
            assert not isinstance(seg, ChildRef)
            if isinstance(seg, RenderedLevel):
                walk(seg)

    walk(level)


class PJXNestedBranches(BaseComponent):
    pass


PJXNestedBranches.__pjx_descriptor__ = descriptor_for(
    PJXNestedBranches, "nested_branches.html"
)


def test_sibling_branches_get_their_own_levels_all_the_way_down(session):
    level = render_level(PJXNestedBranches(), session)
    left, right = level.segments[1], level.segments[3]
    assert isinstance(left, RenderedLevel)
    assert isinstance(right, RenderedLevel)
    assert left is not right
    assert serialize(left) == '<span class="mid">l<em class="leaf">deep</em></span>'
    assert serialize(right) == '<span class="mid">r<em class="leaf">deep</em></span>'


def test_sibling_branches_do_not_share_segment_lists_at_any_depth(session):
    """A shared parse or reused level would make one branch's edit hit both."""
    level = render_level(PJXNestedBranches(), session)
    left, right = level.segments[1], level.segments[3]
    assert isinstance(left, RenderedLevel)
    assert isinstance(right, RenderedLevel)
    assert left.segments is not right.segments
    left_leaf, right_leaf = left.segments[2], right.segments[2]
    assert isinstance(left_leaf, RenderedLevel)
    assert isinstance(right_leaf, RenderedLevel)
    assert left_leaf is not right_leaf
    assert left_leaf.segments is not right_leaf.segments


class PJXMixedMid(BaseComponent):
    label: str = ""


PJXMixedMid.__pjx_descriptor__ = descriptor_for(PJXMixedMid, "nested_mixed_mid.html")


class PJXMixedRoot(BaseComponent):
    pass


PJXMixedRoot.__pjx_descriptor__ = descriptor_for(PJXMixedRoot, "nested_mixed_root.html")


def test_registered_and_unregistered_tags_coexist_at_the_root(session):
    level = render_level(PJXMixedRoot(), session)
    assert isinstance(level.segments[1], RenderedLevel)
    assert level.segments[2] == '<WebThing id="top"/>'


def test_unregistered_tag_inside_a_child_level_also_passes_through(session):
    level = render_level(PJXMixedRoot(), session)
    mid = level.segments[1]
    assert isinstance(mid, RenderedLevel)
    assert isinstance(mid.segments[2], RenderedLevel)
    assert mid.segments[3] == '<OtherThing data-k="v"/>'


def test_mixed_tree_serializes_known_expanded_and_unknown_verbatim(session):
    assert render(PJXMixedRoot(), session) == (
        '<div class="root"><span class="mid">m<em class="leaf">deep</em>'
        '<OtherThing data-k="v"/><OtherThing note="a &amp; b"/></span>'
        '<WebThing id="top"/></div>'
    )


def test_passthrough_reescapes_attr_values(session):
    """Attrs arrive unescaped from the parse, so passthrough must re-escape them."""
    level = render_level(PJXMixedRoot(), session)
    mid = level.segments[1]
    assert isinstance(mid, RenderedLevel)
    assert mid.segments[4] == '<OtherThing note="a &amp; b"/>'


class PJXLoopRoot(BaseComponent):
    items: list[str] = Field(default_factory=list)


PJXLoopRoot.__pjx_descriptor__ = descriptor_for(PJXLoopRoot, "nested_loop.html")


def test_loop_generated_tags_become_rendered_levels(session):
    """ADR 0005: a tag's origin (static markup vs loop output) changes nothing —
    both are cut by the same post-render parse."""
    level = render_level(PJXLoopRoot(items=["a", "b", "c"]), session)
    generated = [seg for seg in level.segments if isinstance(seg, RenderedLevel)]
    assert len(generated) == 3
    assert [serialize(seg) for seg in generated] == [
        '<em class="leaf">a</em>',
        '<em class="leaf">b</em>',
        '<em class="leaf">c</em>',
    ]


def test_loop_generated_levels_are_distinct_objects(session):
    level = render_level(PJXLoopRoot(items=["a", "b"]), session)
    first, second = [seg for seg in level.segments if isinstance(seg, RenderedLevel)]
    assert first is not second
    assert first.segments is not second.segments


def test_loop_with_no_items_produces_no_childrefs(session):
    level = render_level(PJXLoopRoot(items=[]), session)
    assert not any(isinstance(seg, ChildRef) for seg in level.segments)
    assert render(PJXLoopRoot(items=[]), session) == '<ul class="loop"></ul>'


def test_loop_generated_tree_serializes_in_source_order(session):
    assert render(PJXLoopRoot(items=["a", "b"]), session) == (
        '<ul class="loop"><em class="leaf">a</em><em class="leaf">b</em></ul>'
    )


class PJXFullMid(BaseComponent):
    item: str = ""


PJXFullMid.__pjx_descriptor__ = descriptor_for(PJXFullMid, "nested_full_mid.html")


class PJXFullRoot(BaseComponent):
    rows: list[str] = Field(default_factory=list)


PJXFullRoot.__pjx_descriptor__ = descriptor_for(PJXFullRoot, "nested_full_root.html")


def test_generated_mixed_three_level_tree_serializes_end_to_end(session):
    assert render(PJXFullRoot(rows=["x", "y"]), session) == (
        '<div class="root">'
        '<section class="mid"><em class="leaf">x</em><Widget row="x"/></section>'
        '<section class="mid"><em class="leaf">y</em><Widget row="y"/></section>'
        '<WebThing id="top"/>'
        "</div>"
    )


def test_generated_mixed_tree_has_no_surviving_childrefs(session):
    level = render_level(PJXFullRoot(rows=["x", "y"]), session)

    def walk(node: RenderedLevel) -> None:
        for seg in node.segments:
            assert not isinstance(seg, ChildRef)
            if isinstance(seg, RenderedLevel):
                walk(seg)

    walk(level)


def test_generated_mid_levels_each_own_their_generated_leaf(session):
    level = render_level(PJXFullRoot(rows=["x", "y"]), session)
    mids = [seg for seg in level.segments if isinstance(seg, RenderedLevel)]
    assert len(mids) == 2
    leaves = [
        seg for mid in mids for seg in mid.segments if isinstance(seg, RenderedLevel)
    ]
    assert len(leaves) == 2
    assert leaves[0] is not leaves[1]
    assert leaves[0].segments is not leaves[1].segments
    assert serialize(leaves[0]) == '<em class="leaf">x</em>'
    assert serialize(leaves[1]) == '<em class="leaf">y</em>'


class PJXBadLeaf(BaseComponent):
    pass


PJXBadLeaf.__pjx_descriptor__ = descriptor_for(PJXBadLeaf, "nested_bad_leaf.html")


class PJXBadMid(BaseComponent):
    pass


PJXBadMid.__pjx_descriptor__ = descriptor_for(PJXBadMid, "nested_bad_mid.html")


class PJXBadRoot(BaseComponent):
    pass


PJXBadRoot.__pjx_descriptor__ = descriptor_for(PJXBadRoot, "nested_bad_root.html")


def test_grandchild_render_failure_propagates_unchanged(session):
    """Two hops down, the error still names the failing class and its template."""
    discovery._registry.mapping["pjx_bad_leaf"] = PJXBadLeaf
    discovery._registry.mapping["pjx_bad_mid"] = PJXBadMid
    with pytest.raises(ValueError) as excinfo:
        render_level(PJXBadRoot(), session)
    message = str(excinfo.value)
    assert "PJXBadLeaf" in message
    assert "nested_bad_leaf.html" in message
    assert "PJXBadMid" not in message
