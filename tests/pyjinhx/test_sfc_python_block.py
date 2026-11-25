"""The ``{#python ... #}`` block scanner: where a block is, and the Python
source it yields with every line and column left where the file has it."""

import ast
import time

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
    assert (block.open_line, block.close_line) == (1, 7)
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
        "<p></p>\n <p>{#python\nx = 1\n#}",
        "<pre>\n  {#python\n  x = 1\n  #}\n</pre>",
        "<p>{#python\nx = 1\n",
    ],
)
def test_text_that_is_not_an_opener_is_not_a_block(source):
    assert sfc.python_block(source, "card.pjx") is None


@pytest.mark.parametrize(
    ("source", "lineno", "code"),
    [
        ("{#python\nx = 1\n#}\n{#python\ny = 2\n#}", 4, sfc.SECOND_BLOCK),
        ('{#python\nx = "#}"\n#}', 2, sfc.PYTHON_BLOCK_EARLY_CLOSE),
        ('{#python\nx = f"{n:#}"\n#}', 2, sfc.PYTHON_BLOCK_EARLY_CLOSE),
        ("{#python\nx = 1  # done #}\n#}", 2, sfc.PYTHON_BLOCK_EARLY_CLOSE),
        ("{#python\nx = 1\n  #}", 3, sfc.CLOSER_NOT_AT_LINE_START),
        ("{#python\nx = 1\n-#}", 3, sfc.CLOSER_NOT_AT_LINE_START),
        ("{#python\nx = 1\n", 1, sfc.UNCLOSED_BLOCK),
        ("<p></p>\n{#python\n", 2, sfc.UNCLOSED_BLOCK),
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


def test_an_empty_block_has_no_body_lines():
    block = sfc.python_block("{#python\n#}\n<p></p>", "card.pjx")

    assert block is not None
    assert block.body == ""
    assert block.close_line - block.open_line == 1


def test_a_closer_that_is_not_alone_says_so_rather_than_early_close():
    with pytest.raises(SyntaxError, match="alone in column 0"):
        sfc.python_block("{#python\nx = 1\n  #}", "card.pjx")


@pytest.mark.parametrize(
    "source",
    [
        "{% raw %}\n{#python\nx = 1\n#}\n{% endraw %}\n<p></p>",
        '{% set h = "{#" %}\n<p>{{ h }}</p>',
    ],
)
def test_jinja_raw_regions_and_tag_strings_hold_no_blocks(source):
    assert sfc.python_block(source, "card.pjx") is None


def test_a_closer_inside_a_tag_string_does_not_end_a_comment():
    source = '<p>{{ "#}" }}</p>\n{#python\nx = 1\n#}\n'

    block = sfc.python_block(source, "card.pjx")

    assert block is not None
    assert block.open_line == 2


def test_a_comment_opener_inside_a_tag_string_is_not_a_block():
    source = "{{ '\n{#python' }}\nx = 1\n#}\n"

    assert sfc.python_block(source, "card.pjx") is None


def test_read_document_drops_a_byte_order_mark(tmp_path):
    path = tmp_path / "card.pjx"
    path.write_bytes(b"\xef\xbb\xbf{#python\nx = 1\n#}\n<p></p>")

    block = sfc.python_block(sfc.read_document(path, None), "card.pjx")

    assert block is not None
    assert block.open_line == 1


def _seconds(scan, source: str) -> float:
    started = time.perf_counter()
    scan(source, "card.pjx")
    return time.perf_counter() - started


@pytest.mark.parametrize("opener", ["{{ ", "{% "])
def test_an_unclosed_tag_full_of_string_literals_scans_in_linear_time(opener):
    source = opener + '"a" ' * 40

    assert _seconds(sfc.python_block, source) < 1


@pytest.mark.parametrize("unit", ["{{ x\n", "{% raw %}\n", "{# x\n"])
def test_many_unclosed_openers_are_scanned_once(unit):
    assert _seconds(sfc.python_block, unit * 16000) < 1
    assert _seconds(lambda s, f: sfc.strip_to_text(s), unit * 16000) < 1


@pytest.mark.parametrize(
    ("source", "line"),
    [
        ("{#python\nx = 1\n#}\n<p></p>\n", 1),
        ("<p></p>\n{#python \t\r\nx = 1\n#}\n", 2),
        ("{# python\nx = 1\n#}\n", None),
        ("{#python\nnever closed\n", 1),
        ("{# python helpers below #}\n<p></p>\n", None),
        ("{#python is nice #}\n<p></p>\n", None),
        ("<p></p>\n  {#python\nx = 1\n#}\n", None),
        ("{% raw %}\n{#python\nx = 1\n#}\n{% endraw %}\n", None),
        ("{#def #}\n{{ '{#python\\n' }}\n", None),
        ("", None),
    ],
)
def test_an_opener_is_the_whole_line_outside_raw_and_tags(source, line):
    assert sfc.opener_line(source) == line


def test_a_document_without_the_keyword_is_not_lexed(monkeypatch):
    class Unreadable:
        def finditer(self, source):
            raise AssertionError("lexed")

    monkeypatch.setattr(sfc, "_LEXEME_RE", Unreadable())

    assert sfc.opener_line("<p>{{ x }}</p>") is None
    assert sfc.python_block("<p>{# python #}</p>", "card.pjx") is None


def test_a_block_pads_its_body_to_the_files_own_lines():
    block = sfc.python_block("<p></p>\n{#python\nx = 1\n#}\n", "card.pjx")
    assert block is not None
    assert block.source == "\n\nx = 1\n"
    assert (
        sfc.python_source("<p></p>\n{#python\nx = 1\n#}\n", "card.pjx") == block.source
    )


def test_reworded_keeps_the_code_and_place_of_an_error():
    with pytest.raises(sfc.BlockSyntaxError) as raised:
        sfc.python_block("<p></p>\n{#python\nx = 1\n", "card.pjx")
    error = sfc.reworded(raised.value, "other.pjx", "said again")
    assert (error.code, error.msg, error.filename) == (
        sfc.UNCLOSED_BLOCK,
        "said again",
        "other.pjx",
    )
    assert (error.lineno, error.offset) == (raised.value.lineno, raised.value.offset)


def test_normalize_text_drops_the_mark_and_counts_every_line_break_once():
    assert sfc.normalize_text("\ufeffa\r\nb\rc\n") == "a\nb\nc\n"


def test_blank_comments_keeps_the_lines():
    assert sfc.blank_comments("a{#x\ny#}b\n{{ 1 }}") == "a\nb\n{{ 1 }}"


def test_package_root_is_the_highest_directory_of_the_chain(tmp_path):
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    for name in ("a", "a/b", "a/b/c"):
        (tmp_path / name / "__init__.py").write_text("")
    assert sfc.package_root(tmp_path / "a" / "b" / "c") == tmp_path / "a"
    assert sfc.package_root(tmp_path) is None
