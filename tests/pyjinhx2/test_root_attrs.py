import pytest

from pyjinhx2.root_attrs import _override_tag, serialize_attr


def test_serialize_attr_double_quotes_by_default():
    assert serialize_attr("data-x", "1") == 'data-x="1"'


def test_serialize_attr_falls_back_to_single_quotes_when_value_has_double_quote():
    assert serialize_attr("title", 'He said "hi"') == "title='He said \"hi\"'"


def test_serialize_attr_raises_when_value_has_both_quote_kinds():
    with pytest.raises(ValueError):
        serialize_attr("title", "He said \"hi\", it's me")


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
