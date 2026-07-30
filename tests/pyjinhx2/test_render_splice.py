"""Tests for the recursive render + opaque splice of resolved ChildRefs."""

from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.render import render_level
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
    return RenderSession(template_dir="tests/templates")


def test_resolved_childref_is_replaced_by_a_rendered_level(session):
    level = render_level(PJXParent(), session)
    child = level.segments[1]
    assert isinstance(child, RenderedLevel)
    assert child.descriptor is PJXChild.__pjx_descriptor__


def test_spliced_child_carries_its_own_rendered_segments(session):
    level = render_level(PJXParent(), session)
    child = level.segments[1]
    assert serialize(child) == '<span class="child">a</span>'


def test_no_childref_survives_the_fill(session):
    level = render_level(PJXParent(), session)
    assert not any(isinstance(seg, ChildRef) for seg in level.segments)


def test_level_without_childrefs_is_all_strings(session):
    level = render_level(PJXPlain(), session)
    assert level.segments == ['<div class="plain">', "hello", "</div>"]
