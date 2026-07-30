"""Tests for ChildRef registry lookup and unknown-tag passthrough (issue #362)."""

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent
from pyjinhx2.render import _passthrough_markup
from pyjinhx2.segments import ChildRef, RenderedLevel


class PJXButton(BaseComponent):
    pass


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def level(*segments):
    """A RenderedLevel wrapping the given segments, with the rest stubbed out."""
    return RenderedLevel(segments=list(segments), root_span=(0, 0), descriptor=None)


def test_passthrough_self_closing_with_attrs():
    ref = ChildRef(tag="WebThing", attrs={"id": "a", "data-x": "1"}, inner=None)
    assert _passthrough_markup(ref) == '<WebThing id="a" data-x="1"/>'


def test_passthrough_self_closing_without_attrs_has_no_stray_space():
    ref = ChildRef(tag="WebThing", attrs={}, inner=None)
    assert _passthrough_markup(ref) == "<WebThing/>"


def test_passthrough_paired_tag_keeps_inner_between_open_and_close():
    ref = ChildRef(tag="WebThing", attrs={"id": "a"}, inner="<b>hi</b>")
    assert _passthrough_markup(ref) == '<WebThing id="a"><b>hi</b></WebThing>'


def test_passthrough_paired_tag_without_attrs():
    ref = ChildRef(tag="WebThing", attrs={}, inner="hi")
    assert _passthrough_markup(ref) == "<WebThing>hi</WebThing>"


def test_passthrough_escapes_quotes_in_attr_values():
    ref = ChildRef(tag="WebThing", attrs={"title": 'say "hi"'}, inner=None)
    assert _passthrough_markup(ref) == '<WebThing title="say &quot;hi&quot;"/>'


def test_passthrough_keeps_boolean_attr_as_empty_value():
    ref = ChildRef(tag="WebThing", attrs={"disabled": ""}, inner=None)
    assert _passthrough_markup(ref) == '<WebThing disabled=""/>'
