"""PJXStack lays its content out as a flex row or column spaced by the theme's spacing scale."""

import re

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_badge import PJXBadge
from pyjinhx.builtins.ui.pjx_stack import PJXStack
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

GAPS = ["1", "2", "3", "4", "5", "6", "8", "10", "12"]
ALIGNS = ["start", "center", "end", "stretch", "baseline"]
JUSTIFIES = ["start", "center", "end", "between", "around", "evenly"]


def _html(**kw) -> str:
    return render(PJXStack(id="s", **kw), RenderSession())


def _class_attr(html: str) -> str:
    """Return the root element's class value: the first class="..." in html."""
    match = re.search(r'class="([^"]*)"', html)
    assert match is not None, html
    return match.group(1)


def test_default_render():
    html = _html()
    assert html.count("<div") == 1
    assert 'id="s"' in html
    assert _class_attr(html) == "pjx-stack pjx-stack--vertical pjx-stack--gap-3"
    for unwanted in ("--align-", "--justify-", "--wrap", "role=", "aria-"):
        assert unwanted not in html


def test_horizontal_direction():
    classes = _class_attr(_html(direction="horizontal")).split()
    assert "pjx-stack--horizontal" in classes
    assert "pjx-stack--vertical" not in classes


@pytest.mark.parametrize("gap", GAPS)
def test_every_gap_step_renders_one_gap_class(gap):
    classes = _class_attr(_html(gap=gap)).split()
    gap_classes = [name for name in classes if name.startswith("pjx-stack--gap-")]
    assert gap_classes == [f"pjx-stack--gap-{gap}"]


@pytest.mark.parametrize("align", ALIGNS)
def test_align_values(align):
    assert f"pjx-stack--align-{align}" in _class_attr(_html(align=align)).split()


@pytest.mark.parametrize("justify", JUSTIFIES)
def test_justify_values(justify):
    classes = _class_attr(_html(justify=justify)).split()
    assert f"pjx-stack--justify-{justify}" in classes


def test_wrap_adds_the_wrap_class_and_default_omits_it():
    assert "pjx-stack--wrap" in _class_attr(_html(wrap=True)).split()
    assert "pjx-stack--wrap" not in _class_attr(_html()).split()


def test_class_order_with_every_modifier_and_class_name():
    html = _html(
        direction="horizontal",
        gap="8",
        align="center",
        justify="between",
        wrap=True,
        class_name="x y",
    )
    assert _class_attr(html) == (
        "pjx-stack pjx-stack--horizontal pjx-stack--gap-8 pjx-stack--align-center"
        " pjx-stack--justify-between pjx-stack--wrap x y"
    )


def test_empty_class_name_adds_no_trailing_space():
    assert _class_attr(_html(class_name="")) == (
        "pjx-stack pjx-stack--vertical pjx-stack--gap-3"
    )


def test_class_name_naming_a_modifier_passes_through_once():
    classes = _class_attr(_html(class_name="pjx-stack--wrap")).split()
    assert classes.count("pjx-stack--wrap") == 1
    assert classes[-1] == "pjx-stack--wrap"


def test_extra_attrs_render_on_the_root():
    html = _html(extra_attrs={"data-k": "v", "hx-get": "/p"})
    assert 'data-k="v"' in html
    assert 'hx-get="/p"' in html
    # Both sit inside the root's opening tag, not on some child.
    assert html.index('hx-get="/p"') < html.index(">")


def test_class_name_and_extra_attrs_are_escaped():
    html = _html(class_name="a><script>", extra_attrs={"data-k": "<&", "title": 'a"b'})
    assert "<script>" not in html
    assert "a&gt;&lt;script&gt;" in html
    assert 'data-k="&lt;&amp;"' in html
    assert 'title="a&#34;b"' in html


def test_string_content_renders_raw():
    assert "<b>x</b>" in _html(content="<b>x</b>")


def test_nested_stack_keeps_its_modifiers_off_the_outer_root():
    html = _html(content=PJXStack(id="inner", direction="horizontal"))
    assert html.count("<div") == 2
    assert '<div id="inner" class="pjx-stack pjx-stack--horizontal' in html
    assert "--horizontal" not in _class_attr(html)
    assert html.index('id="s"') < html.index('id="inner"')
    assert html.endswith("</div></div>")


def test_component_content_renders_its_html():
    html = _html(content=PJXBadge(id="b", label="New"))
    assert '<span id="b" class="pjx-badge' in html


def test_empty_stack_has_no_inner_html():
    assert _html().endswith('pjx-stack--gap-3"></div>')


def test_vertical_baseline_is_legal():
    classes = _class_attr(_html(direction="vertical", align="baseline")).split()
    assert "pjx-stack--vertical" in classes
    assert "pjx-stack--align-baseline" in classes


def test_omitted_id_gets_an_auto_pjx_id():
    html = render(PJXStack(), RenderSession())
    assert re.match(r'<div id="pjx-\d+" class="pjx-stack ', html)


@pytest.mark.parametrize(
    "kw",
    [
        {"direction": "row"},
        {"gap": "7"},
        {"gap": "0"},
        {"gap": 3},
        {"align": "flex-start"},
        {"justify": "space-between"},
        {"class_name": 'a"b'},
        {"extra_attrs": {"data-k": "a\"b'c"}},
    ],
    ids=[
        "direction-row",
        "gap-7",
        "gap-0",
        "gap-int-3",
        "align-flex-start",
        "justify-space-between",
        "class-name-quote",
        "extra-attrs-both-quotes",
    ],
)
def test_invalid_values_are_rejected(kw):
    with pytest.raises(ValidationError):
        PJXStack(id="s", **kw)
