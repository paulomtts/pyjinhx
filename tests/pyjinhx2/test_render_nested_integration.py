"""End-to-end integration tests for the ChildRef fill across nested trees.

Composes resolve + instantiate + recurse + splice on deeper, mixed and
loop-generated trees than the per-feature files cover. Tests only: no
production code change was needed to make them pass.
"""

from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.render import render, render_level
from pyjinhx2.segments import ChildRef, RenderedLevel, serialize
from pyjinhx2.session import RenderSession


def descriptor_for(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    """Attach a minimal descriptor pointing at a fixture template."""
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=frozenset(),
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
    }
    yield
    discovery._registry.mapping = {}


@pytest.fixture
def session():
    return RenderSession(template_dir="tests/templates")


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
        '<div class="root"><span class="mid">m'
        '<em class="leaf">deep</em></span></div>'
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
