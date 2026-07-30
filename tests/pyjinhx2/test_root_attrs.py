import pytest

from pyjinhx2.root_attrs import _override_tag, serialize_attr, stamp_root_attrs
from pyjinhx2.segments import RenderedLevel


def _level(markup: str, root_span: tuple[int, int]) -> RenderedLevel:
    return RenderedLevel(segments=[markup], root_span=root_span, descriptor=None)


def test_serialize_attr_double_quotes_by_default():
    assert serialize_attr("data-x", "1") == 'data-x="1"'


def test_serialize_attr_falls_back_to_single_quotes_when_value_has_double_quote():
    assert serialize_attr("title", 'He said "hi"') == "title='He said \"hi\"'"


def test_serialize_attr_raises_when_value_has_both_quote_kinds():
    with pytest.raises(ValueError):
        serialize_attr("title", 'He said "hi", it\'s me')


def test_override_tag_appends_new_attr_before_closing_angle_bracket():
    assert _override_tag('<div class="root">', {"data-x": "1"}) == (
        '<div class="root" data-x="1">'
    )


def test_override_tag_appends_new_attr_on_self_closing_tag_no_double_space():
    result = _override_tag("<br/>", {"data-y": "1"})
    assert result == '<br data-y="1"/>'
    assert "  " not in result


def test_override_tag_appends_multiple_attrs_in_order():
    result = _override_tag("<div>", {"data-a": "1", "data-b": "2"})
    assert result == '<div data-a="1" data-b="2">'


def test_override_tag_replaces_existing_attr_wholesale_not_merged():
    result = _override_tag('<div class="a">', {"class": "b"})
    assert result == '<div class="b">'
    assert "a" not in result.split('"')[1]


def test_override_tag_replaces_existing_attr_single_quoted():
    result = _override_tag("<div class='a'>", {"class": "b"})
    assert result == '<div class="b">'


def test_stamp_root_attrs_no_attrs_is_identity_noop():
    level = _level('<div class="root">hi</div>', (0, 18))
    original_segments_id = id(level.segments[0])
    result = stamp_root_attrs(level, {})
    assert result is level
    assert result.segments[0] == '<div class="root">hi</div>'
    assert result.root_span == (0, 18)
    # identity no-op: same string object, not a re-built equal one
    assert id(result.segments[0]) == original_segments_id


def test_stamp_root_attrs_only_touches_opening_tag_span():
    markup = '<div class="root"><span>child text</span></div>'
    # root_span covers exactly `<div class="root">`
    level = _level(markup, (0, 18))
    stamp_root_attrs(level, {"data-x": "1"})
    stamped = level.segments[0]
    assert stamped.startswith('<div class="root" data-x="1">')  # type: ignore[union-attr]
    # everything after the original root tag is untouched
    assert stamped[len('<div class="root" data-x="1">') :] == (markup[18:])  # type: ignore[index]


def test_stamp_root_attrs_updates_root_span_to_new_tag_length():
    markup = '<div class="root">hi</div>'
    level = _level(markup, (0, 18))
    stamp_root_attrs(level, {"data-x": "1"})
    start, end = level.root_span
    assert start == 0
    assert level.segments[0][start:end] == '<div class="root" data-x="1">'  # type: ignore[index]


def test_stamp_root_attrs_idempotent_no_duplicate_attrs():
    level = _level('<div class="root">hi</div>', (0, 18))
    stamp_root_attrs(level, {"class": "stamped"})
    first = level.segments[0]
    # stamp the same attrs again onto the already-stamped tag
    stamp_root_attrs(level, {"class": "stamped"})
    second = level.segments[0]
    assert first == second
    assert second.count("class=") == 1  # type: ignore[union-attr]


def test_stamp_root_attrs_multiple_attrs_via_rendered_level():
    level = _level('<div class="root">hi</div>', (0, 18))
    stamp_root_attrs(level, {"data-a": "1", "data-b": "2"})
    start, end = level.root_span
    assert level.segments[0][start:end] == ('<div class="root" data-a="1" data-b="2">')  # type: ignore[index]
    assert level.segments[0][end:] == "hi</div>"  # type: ignore[index]
