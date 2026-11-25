"""The ``{#python ... #}`` block scanner: where a block is, and the Python
source it yields with every line and column left where the file has it."""

import ast

import pytest

from pyjinhx import sfc

SOURCE = """{#python
from pyjinhx import ReactiveComponent


class TodoCount(ReactiveComponent):
    remaining: int = 0
#}
<div class="counter">{{ remaining }} left</div>
{#css
.counter { font-weight: 600; }
#}
"""


def test_the_block_reports_its_lines_and_body():
    block = sfc.python_block(SOURCE, "card.pjx")

    assert block is not None
    assert (block.open_line, block.first_line, block.last_line, block.close_line) == (
        1,
        2,
        6,
        7,
    )
    assert block.body.startswith("from pyjinhx import ReactiveComponent\n")
    assert block.body.endswith("    remaining: int = 0\n")


def test_no_block_is_none():
    assert sfc.python_block("<p>hi</p>", "card.pjx") is None
    assert sfc.python_source("<p>hi</p>", "card.pjx") is None


def test_the_source_puts_each_line_and_column_where_the_file_has_it():
    tree = ast.parse(sfc.python_source(SOURCE, "card.pjx") or "")

    card = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert card.lineno == 5
    annotated = card.body[0]
    assert isinstance(annotated, ast.AnnAssign)
    assert (annotated.target.lineno, annotated.target.col_offset) == (6, 4)


def test_a_block_after_markup_and_a_css_block_keeps_its_lines():
    source = (
        '<div class="a">hi</div>\n'
        "{#css\n.a { color: red; }\n#}\n"
        "{#python\nimport os\n\nclass Card:\n    pass\n#}\n"
    )

    tree = ast.parse(sfc.python_source(source, "card.pjx") or "")

    assert tree.body[0].lineno == 6
    assert tree.body[1].lineno == 8


@pytest.mark.parametrize(
    "source",
    [
        "{# python\nx = 1\n#}",
        "{#python x = 1 #}",
        "{#-python\nx = 1\n#}",
        "{#pythonic\nx = 1\n#}",
    ],
)
def test_text_that_is_not_an_opener_is_not_a_block(source):
    assert sfc.python_block(source, "card.pjx") is None


@pytest.mark.parametrize(
    ("source", "lineno", "code"),
    [
        ("<p></p>\n <p>{#python\nx = 1\n#}", 2, sfc.OPENER_NOT_AT_LINE_START),
        ("{#python\nx = 1\n#}\n{#python\ny = 2\n#}", 4, sfc.SECOND_BLOCK),
        ('{#python\nx = "#}"\n#}', 2, sfc.PYTHON_BLOCK_EARLY_CLOSE),
        ('{#python\nx = f"{n:#}"\n#}', 2, sfc.PYTHON_BLOCK_EARLY_CLOSE),
        ("{#python\nx = 1  # done #}\n#}", 2, sfc.PYTHON_BLOCK_EARLY_CLOSE),
        ("{#python\nx = 1\n  #}", 3, sfc.PYTHON_BLOCK_EARLY_CLOSE),
        ("{#python\nx = 1\n#} <p></p>", 3, sfc.TEXT_AFTER_CLOSER),
    ],
)
def test_a_malformed_block_is_a_syntax_error_at_its_line(source, lineno, code):
    with pytest.raises(sfc.BlockSyntaxError) as raised:
        sfc.python_block(source, "card.pjx")

    assert raised.value.filename == "card.pjx"
    assert raised.value.lineno == lineno
    assert raised.value.code == code


def test_an_early_close_names_the_fix():
    with pytest.raises(SyntaxError, match=r'"#" "}"'):
        sfc.python_block('{#python\nx = "#}"\n#}', "card.pjx")


def test_a_body_line_that_is_only_the_closer_ends_the_block_there():
    block = sfc.python_block("{#python\nx = 1\n#}\ny = 2\n#}\n", "card.pjx")

    assert block is not None
    assert block.body == "x = 1\n"
    assert block.close_line == 3


def test_spaces_and_tabs_around_the_opener_and_closer_are_fine():
    block = sfc.python_block("{#python \t\nx = 1\n#}  \t\n", "card.pjx")

    assert block is not None
    assert block.body == "x = 1\n"


def test_crlf_line_endings_give_the_same_lines():
    source = SOURCE.replace("\n", "\r\n")

    block = sfc.python_block(source, "card.pjx")
    tree = ast.parse(sfc.python_source(source, "card.pjx") or "")

    assert block is not None
    assert (block.open_line, block.close_line) == (1, 7)
    assert next(n for n in tree.body if isinstance(n, ast.ClassDef)).lineno == 5


def test_an_empty_block_has_an_empty_body_range():
    block = sfc.python_block("{#python\n#}\n<p></p>", "card.pjx")

    assert block is not None
    assert block.body == ""
    assert block.last_line < block.first_line
