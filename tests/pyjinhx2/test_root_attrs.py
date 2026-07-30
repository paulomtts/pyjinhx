import pytest

from pyjinhx2.root_attrs import serialize_attr


def test_serialize_attr_double_quotes_by_default():
    assert serialize_attr("data-x", "1") == 'data-x="1"'


def test_serialize_attr_falls_back_to_single_quotes_when_value_has_double_quote():
    assert serialize_attr("title", 'He said "hi"') == "title='He said \"hi\"'"


def test_serialize_attr_raises_when_value_has_both_quote_kinds():
    with pytest.raises(ValueError):
        serialize_attr("title", "He said \"hi\", it's me")
