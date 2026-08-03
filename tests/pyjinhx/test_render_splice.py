"""Tests for the recursive render + opaque splice of resolved ChildRefs."""

from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.component import BaseComponent
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


class PJXChild(BaseComponent):
    label: str = ""


PJXChild.__pjx_descriptor__ = descriptor_for(PJXChild, "splice_child.html")


class PJXParent(BaseComponent):
    pass


PJXParent.__pjx_descriptor__ = descriptor_for(PJXParent, "splice_parent.html")


class PJXPlain(BaseComponent):
    pass


PJXPlain.__pjx_descriptor__ = descriptor_for(PJXPlain, "splice_plain.html")


@pytest.fixture(autouse=True)
def registry():
    """Each test starts from a mapping holding just the fixture components."""
    discovery._registry.mapping = {"pjx_child": PJXChild}
    yield
    discovery._registry.mapping = {}


@pytest.fixture
def session():
    return RenderSession()


def test_resolved_childref_is_replaced_by_a_rendered_level(session):
    level = render_level(PJXParent(), session)
    child = level.segments[1]
    assert isinstance(child, RenderedLevel)
    assert child.descriptor is PJXChild.__pjx_descriptor__


def test_spliced_child_carries_its_own_rendered_segments(session):
    level = render_level(PJXParent(), session)
    child = level.segments[1]
    assert isinstance(child, RenderedLevel)
    assert serialize(child) == '<span class="child">a</span>'


def test_no_childref_survives_the_fill(session):
    level = render_level(PJXParent(), session)
    assert not any(isinstance(seg, ChildRef) for seg in level.segments)


def test_level_without_childrefs_is_all_strings(session):
    level = render_level(PJXPlain(), session)
    assert level.segments == ['<div class="plain">', "hello", "</div>"]


class PJXSiblings(BaseComponent):
    pass


PJXSiblings.__pjx_descriptor__ = descriptor_for(PJXSiblings, "splice_siblings.html")


class PJXMixed(BaseComponent):
    pass


PJXMixed.__pjx_descriptor__ = descriptor_for(PJXMixed, "splice_mixed.html")


def test_each_sibling_childref_gets_its_own_rendered_level(session):
    level = render_level(PJXSiblings(), session)
    first, second = level.segments[1], level.segments[3]
    assert isinstance(first, RenderedLevel)
    assert isinstance(second, RenderedLevel)
    assert first is not second
    assert serialize(first) == '<span class="child">a</span>'
    assert serialize(second) == '<span class="child">b</span>'


def test_siblings_do_not_share_segment_lists(session):
    """A shared parse or a reused level would make one sibling's edit hit both."""
    level = render_level(PJXSiblings(), session)
    first, second = level.segments[1], level.segments[3]
    assert isinstance(first, RenderedLevel)
    assert isinstance(second, RenderedLevel)
    assert first.segments is not second.segments


def test_passthrough_string_is_untouched_next_to_a_splice(session):
    level = render_level(PJXMixed(), session)
    assert isinstance(level.segments[1], RenderedLevel)
    assert level.segments[2] == '<WebThing id="w"/>'


class PJXBadChild(BaseComponent):
    pass


PJXBadChild.__pjx_descriptor__ = descriptor_for(PJXBadChild, "splice_bad_child.html")


class PJXBadParent(BaseComponent):
    pass


PJXBadParent.__pjx_descriptor__ = descriptor_for(PJXBadParent, "splice_bad_parent.html")


def test_serialize_nests_the_spliced_child_in_the_parent_output(session):
    assert render(PJXParent(), session) == (
        '<div class="parent"><span class="child">a</span></div>'
    )


def test_serialize_nests_both_siblings_in_order(session):
    assert render(PJXSiblings(), session) == (
        '<div class="parent"><span class="child">a</span><hr/>'
        '<span class="child">b</span></div>'
    )


def test_child_render_failure_propagates_unchanged(session):
    discovery._registry.mapping["pjx_bad_child"] = PJXBadChild
    with pytest.raises(ValueError) as excinfo:
        render_level(PJXBadParent(), session)
    assert "PJXBadChild" in str(excinfo.value)
    assert "splice_bad_child.html" in str(excinfo.value)
