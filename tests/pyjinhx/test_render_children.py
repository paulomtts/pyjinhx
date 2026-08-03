"""Tests for ChildRef registry lookup and unknown-tag passthrough (issue #362)."""

from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.render import _fill_children, _passthrough_markup
from pyjinhx.segments import ChildRef, RenderedLevel


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


def test_unresolved_tag_becomes_passthrough_string():
    lvl = level("<div>", ChildRef(tag="WebThing", attrs={}, inner=None), "</div>")
    _fill_children(lvl)
    assert lvl.segments == ["<div>", "<WebThing/>", "</div>"]


def test_resolved_tag_is_left_as_a_childref():
    discovery._registry.mapping = {"pjx_button": PJXButton}
    ref = ChildRef(tag="PJXButton", attrs={}, inner=None)
    lvl = level(ref)
    _fill_children(lvl)
    assert lvl.segments == [ref]
    assert isinstance(lvl.segments[0], ChildRef)


def test_pascal_tag_is_converted_to_snake_before_lookup():
    """The registry is keyed snake_case; skipping the conversion would always miss."""
    discovery._registry.mapping = {"pjx_button": PJXButton}
    lvl = level(ChildRef(tag="PJXButton", attrs={}, inner=None))
    _fill_children(lvl)
    assert isinstance(lvl.segments[0], ChildRef)


def test_tag_whose_snake_form_is_unregistered_still_passes_through():
    discovery._registry.mapping = {"pjx_button": PJXButton}
    lvl = level(ChildRef(tag="PJXButtons", attrs={}, inner=None))
    _fill_children(lvl)
    assert lvl.segments == ["<PJXButtons/>"]


def test_mixed_segments_replace_only_the_miss_and_keep_order():
    discovery._registry.mapping = {"pjx_button": PJXButton}
    hit = ChildRef(tag="PJXButton", attrs={}, inner=None)
    lvl = level("<div>", hit, ChildRef(tag="WebThing", attrs={}, inner="x"), "</div>")
    _fill_children(lvl)
    assert lvl.segments == ["<div>", hit, "<WebThing>x</WebThing>", "</div>"]


def test_level_without_childrefs_is_untouched():
    lvl = level("<div>", "hello", "</div>")
    _fill_children(lvl)
    assert lvl.segments == ["<div>", "hello", "</div>"]


def test_unknown_tag_raises_nothing():
    lvl = level(ChildRef(tag="TotallyUnknown", attrs={"a": "b"}, inner=None))
    _fill_children(lvl)
    assert lvl.segments == ['<TotallyUnknown a="b"/>']


def test_render_level_passes_unknown_tags_through():
    from pyjinhx.render import render, render_level
    from pyjinhx.session import RenderSession

    class UnknownHost(BaseComponent):
        pass

    UnknownHost.__pjx_descriptor__ = ClassDescriptor(
        template_path=Path("unknown_host.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": UnknownHost},
    )

    session = RenderSession(template_dir="tests/templates")
    lvl = render_level(UnknownHost(), session)
    assert all(isinstance(seg, str) for seg in lvl.segments)
    assert render(UnknownHost(), session) == '<div><WebThing id="a"/></div>'
