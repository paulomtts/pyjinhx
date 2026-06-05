import pytest

from pyjinhx.utils import stamp_root_attributes


def test_stamps_into_first_start_tag():
    result = stamp_root_attributes('<div class="x">hi</div>', {"data-pjx-id": "a"})
    assert result == '<div class="x" data-pjx-id="a">hi</div>'


def test_stamps_multiple_attributes_in_order():
    result = stamp_root_attributes("<span>1</span>", {"data-a": "1", "data-b": "2"})
    assert result == '<span data-a="1" data-b="2">1</span>'


def test_stamps_self_closing_tag_before_slash():
    result = stamp_root_attributes('<img src="a.png"/>', {"data-pjx-id": "a"})
    assert result == '<img src="a.png" data-pjx-id="a"/>'


def test_skips_leading_whitespace_and_comments():
    result = stamp_root_attributes(
        "\n  <!-- note --><section>x</section>", {"data-pjx-id": "a"}
    )
    assert result == '\n  <!-- note --><section data-pjx-id="a">x</section>'


def test_is_quote_aware_for_gt_inside_attribute_value():
    result = stamp_root_attributes('<div data-q="a>b">y</div>', {"data-pjx-id": "a"})
    assert result == '<div data-q="a>b" data-pjx-id="a">y</div>'


def test_escapes_double_quotes_in_values():
    result = stamp_root_attributes("<div>x</div>", {"data-pjx-id": 'a"b'})
    assert result == '<div data-pjx-id="a&quot;b">x</div>'


def test_empty_attributes_returns_input_unchanged():
    assert stamp_root_attributes("<div>x</div>", {}) == "<div>x</div>"


def test_raises_when_no_root_element():
    with pytest.raises(ValueError, match="no root HTML element"):
        stamp_root_attributes("just text, no tags", {"data-pjx-id": "a"})
