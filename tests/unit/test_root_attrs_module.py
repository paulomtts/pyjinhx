import pytest

from pyjinhx.root_attrs import apply_root_attrs, find_single_root, serialize_attr


def test_serialize_attr_prefers_double_quotes():
    assert serialize_attr("data-x", "y") == 'data-x="y"'


def test_serialize_attr_falls_back_to_single_quotes():
    assert serialize_attr("hx-headers", '{"a": "b"}') == "hx-headers='{\"a\": \"b\"}'"


def test_serialize_attr_both_quote_types_raises():
    with pytest.raises(ValueError, match="both"):
        serialize_attr("data-x", "a\"b'c")


def test_find_single_root_returns_span_of_opening_tag():
    html = "  <article class=\"c\">body</article>"
    start, end = find_single_root(html, component_name="X")
    assert html[start:end] == '<article class="c">'


def test_find_single_root_ignores_leading_comment_and_whitespace():
    html = "<!-- hi -->\n<div>x</div>"
    start, end = find_single_root(html, component_name="X")
    assert html[start:end] == "<div>"


def test_find_single_root_allows_void_root():
    html = '<input type="text">'
    start, end = find_single_root(html, component_name="X")
    assert html[start:end] == '<input type="text">'


def test_find_single_root_allows_self_closing_root():
    start, end = find_single_root("<br/>", component_name="X")
    assert (start, end) == (0, 5)


def test_find_single_root_rejects_two_top_level_elements():
    with pytest.raises(ValueError, match="exactly one root"):
        find_single_root("<div>a</div><div>b</div>", component_name="Widget")


def test_find_single_root_rejects_zero_elements():
    with pytest.raises(ValueError, match="exactly one root"):
        find_single_root("just text", component_name="Widget")


def test_apply_root_attrs_appends_non_colliding_attr():
    html = '<article class="c">x</article>'
    out = apply_root_attrs(html, component_name="X", attrs={"data-y": "1"})
    assert out == '<article class="c" data-y="1">x</article>'


def test_apply_root_attrs_overrides_colliding_attr():
    html = '<article class="card">x</article>'
    out = apply_root_attrs(html, component_name="X", attrs={"class": "mt-4"})
    assert out == '<article class="mt-4">x</article>'


def test_apply_root_attrs_injects_into_void_root():
    html = '<input type="text">'
    out = apply_root_attrs(html, component_name="X", attrs={"data-y": "1"})
    assert out == '<input type="text" data-y="1">'


def test_apply_root_attrs_injects_before_self_closing_slash():
    html = "<br/>"
    out = apply_root_attrs(html, component_name="X", attrs={"data-y": "1"})
    assert out == '<br data-y="1"/>'


def test_apply_root_attrs_empty_attrs_still_validates():
    with pytest.raises(ValueError, match="exactly one root"):
        apply_root_attrs("<div></div><div></div>", component_name="X", attrs={})


def test_apply_root_attrs_empty_attrs_returns_unchanged():
    html = "<div>x</div>"
    assert apply_root_attrs(html, component_name="X", attrs={}) == html


def test_apply_root_attrs_handles_multiline_root_tag():
    html = '<div\n  id="a"\n  class="c">body</div>'
    out = apply_root_attrs(html, component_name="X", attrs={"data-y": "1"})
    assert 'data-y="1"' in out
    # injected attr lands inside the opening tag, before the closing '>'
    assert out.index('data-y="1"') < out.index('>')
    assert "body</div>" in out


def test_find_single_root_returns_span_of_multiline_opening_tag():
    html = '<div\n  id="a"\n  class="c">body</div>'
    start, end = find_single_root(html, component_name="X")
    # The span must cover the entire multi-line opening tag up to and including '>'
    assert html[start:end] == '<div\n  id="a"\n  class="c">'
