import pytest

from pyjinhx.root_attrs import (
    RootStampCollisionError,
    _override_tag,
    serialize_attr,
    stamp_root_attrs,
)
from pyjinhx.segments import RenderedLevel


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


def test_stamp_root_attrs_with_whitespace_prologue_keeps_root_span_absolute():
    # segments[0] is a whitespace-only prologue segment; the real root tag
    # lives in segments[1], and root_span is absolute over the raw source
    # (i.e. offset as if segments[0] and segments[1] were concatenated).
    prologue = "\n  "
    tag = '<div class="root">hi</div>'
    level = RenderedLevel(
        segments=[prologue, tag],
        root_span=(len(prologue) + 0, len(prologue) + 18),
        descriptor=None,
    )
    stamp_root_attrs(level, {"data-x": "1"})
    start, end = level.root_span
    # root_span must still be absolute (rebased past the prologue), so a
    # caller slicing segments[1] with root_span - len(prologue) gets the tag.
    local_start, local_end = start - len(prologue), end - len(prologue)
    assert level.segments[1][local_start:local_end] == (  # type: ignore[index]
        '<div class="root" data-x="1">'
    )


def test_stamp_root_attrs_with_whitespace_prologue_is_idempotent_across_two_calls():
    # A second stamp call (e.g. re-stamping via oob_swaps) must not re-subtract
    # the prologue's length from an already-rebased root_span.
    prologue = "\n  "
    tag = '<div class="root">hi</div>'
    level = RenderedLevel(
        segments=[prologue, tag],
        root_span=(len(prologue), len(prologue) + 18),
        descriptor=None,
    )
    stamp_root_attrs(level, {"data-a": "1"})
    stamp_root_attrs(level, {"data-b": "2"})
    start, end = level.root_span
    local_start, local_end = start - len(prologue), end - len(prologue)
    assert level.segments[1][local_start:local_end] == (  # type: ignore[index]
        '<div class="root" data-a="1" data-b="2">'
    )


def test_stamp_root_attrs_all_whitespace_segments_raises():
    level = RenderedLevel(segments=["   ", "\n"], root_span=(0, 0), descriptor=None)
    with pytest.raises(ValueError):
        stamp_root_attrs(level, {"data-x": "1"})


def test_stamp_root_attrs_nested_reactive_collision_raises():
    """Stamping a nested reactive root that already carries all three reactive
    identity attrs with attrs that include one of those keys raises
    RootStampCollisionError, preventing silent overwrite of the child's id."""
    # Inner level's tag with all three reactive stamps
    inner_tag = (
        '<div data-pjx-id="inner-123" data-pjx-type="inner_comp" data-pjx-hash="abc">'
    )
    inner_level = _level(inner_tag, (0, len(inner_tag)))

    # Outer level whose root segment is the inner level (component template = another component)
    outer_level = RenderedLevel(
        segments=[inner_level], root_span=(0, len(inner_tag)), descriptor=None
    )

    # Attempting to stamp the outer component's reactive identity onto the nested root
    # should raise, not silently overwrite the inner component's identity
    with pytest.raises(RootStampCollisionError) as exc_info:
        stamp_root_attrs(
            outer_level,
            {
                "data-pjx-id": "outer-456",
                "data-pjx-type": "outer_comp",
                "data-pjx-hash": "def",
            },
        )

    assert "cannot stamp a reactive root tag" in str(exc_info.value)
    assert "inner-123" in str(exc_info.value)
    assert "outer-456" in str(exc_info.value)


def test_stamp_root_attrs_nested_reactive_exact_restamp_is_noop():
    """A component whose whole template is one child tag can be stamped with
    the *same* identity values that already sit on the nested root (e.g. the
    on_rendered subscriber and an explicit OOB stamp both firing in the same
    render pass) without raising: the values agree, so this is one component
    re-asserting its own identity, not a boundary violation (issue #1020)."""
    inner_tag = (
        '<div data-pjx-id="same-123" data-pjx-type="same_comp" data-pjx-hash="abc">'
    )
    inner_level = _level(inner_tag, (0, len(inner_tag)))

    outer_level = RenderedLevel(
        segments=[inner_level], root_span=(0, len(inner_tag)), descriptor=None
    )

    stamp_root_attrs(
        outer_level,
        {
            "data-pjx-id": "same-123",
            "data-pjx-type": "same_comp",
            "data-pjx-hash": "abc",
        },
    )
    assert outer_level is not None


def test_stamp_root_attrs_nested_partial_reactive_does_not_collide():
    """A nested reactive root with only some of the identity attrs (not a
    complete stamp) can still be stamped without collision, allowing partial
    overwrites."""
    # Inner level with only some reactive stamps (not all three)
    inner_tag = '<div data-pjx-id="inner-123" data-pjx-type="inner_comp">'
    inner_level = _level(inner_tag, (0, len(inner_tag)))

    outer_level = RenderedLevel(
        segments=[inner_level], root_span=(0, len(inner_tag)), descriptor=None
    )

    # Since the inner tag doesn't have all three stamps, this should not raise
    stamp_root_attrs(
        outer_level,
        {
            "data-pjx-id": "outer-456",
            "data-pjx-type": "outer_comp",
            "data-pjx-hash": "def",
        },
    )
    # Should complete without error
    assert outer_level is not None


def test_stamp_root_attrs_nested_same_level_override_allowed():
    """Stamping a nested RenderedLevel with no reactive stamps allows it,
    and stamping the same level multiple times (re-stamping) overwrites."""
    # Inner level with no reactive stamps
    inner_tag = "<div>"
    inner_level = _level(inner_tag, (0, len(inner_tag)))

    outer_level = RenderedLevel(
        segments=[inner_level], root_span=(0, len(inner_tag)), descriptor=None
    )

    # First stamp should work
    stamp_root_attrs(
        outer_level,
        {"data-pjx-id": "first-id", "data-pjx-type": "first_type"},
    )

    # Re-stamping the same nested level should also work (it's own level override)
    stamp_root_attrs(
        outer_level,
        {"data-pjx-id": "second-id", "data-pjx-type": "second_type"},
    )

    assert outer_level is not None
