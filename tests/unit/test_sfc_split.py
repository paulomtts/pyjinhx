import pytest

from pyjinhx.sfc import split_pjx


def test_no_block_returns_none_and_full_source():
    src = "<div>{{ title }}</div>\n"
    python_src, template_src = split_pjx(src)
    assert python_src is None
    assert template_src == src


def test_extracts_block_and_template():
    src = (
        "{# python\n"
        "class Counter(BaseComponent):\n"
        "    remaining: int\n"
        "#}\n"
        "<div>{{ remaining }} left</div>\n"
    )
    python_src, template_src = split_pjx(src)
    assert "class Counter(BaseComponent):" in python_src
    assert "    remaining: int" in python_src
    assert template_src == "<div>{{ remaining }} left</div>\n"


def test_python_src_is_line_aligned():
    src = "{# python\nx = 1\n#}\n<p></p>\n"
    python_src, _ = split_pjx(src)
    # opener is file line 1, so `x = 1` must land on line 2
    assert python_src.splitlines()[1] == "x = 1"
    assert python_src.splitlines()[0] == ""


def test_leading_blank_lines_allowed_before_opener():
    src = "\n\n{# python\nx = 1\n#}\n<p></p>\n"
    python_src, template_src = split_pjx(src)
    assert "x = 1" in python_src
    assert template_src == "<p></p>\n"


def test_inline_hash_brace_inside_python_is_safe():
    src = "{# python\nd = {}  # not a closer #}\nclass C: ...\n#}\n<p></p>\n"
    python_src, template_src = split_pjx(src)
    assert "d = {}" in python_src
    assert "class C: ..." in python_src
    assert template_src == "<p></p>\n"


def test_opener_must_be_alone_on_its_line():
    with pytest.raises(ValueError, match="alone on its line"):
        split_pjx("{# python x = 1\n#}\n<p></p>\n")


def test_unterminated_block_raises():
    with pytest.raises(ValueError, match="unterminated"):
        split_pjx("{# python\nx = 1\n<p></p>\n")
