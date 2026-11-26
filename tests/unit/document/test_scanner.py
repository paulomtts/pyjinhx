"""Tests for reading a component's inline template out of its module source."""

import ast
import textwrap
import time

import jinja2
import pytest

from pyjinhx.document import scanner
from pyjinhx.document.scanner import (
    HeaderSignatureError,
    extract_template,
    header_arguments,
    read_document,
    source_segment,
)

BADGE = textwrap.dedent('''\
    from pyjinhx import BaseComponent


    class Badge(BaseComponent):
        label: str

        template = """
        <span class="badge">
          {{ label }}
        </span>
        """
    ''')


def render(source: str, **context: object) -> str:
    return jinja2.Environment().from_string(source).render(**context)


def test_the_template_renders_without_its_indentation_or_blank_edges():
    template = extract_template(BADGE, "Badge")
    assert render(template, label="new") == '<span class="badge">\n  new\n</span>'


def test_each_template_line_keeps_its_line_number_from_the_module():
    template = extract_template(BADGE, "Badge")
    module_lines = BADGE.splitlines()
    template_lines = template.splitlines()
    assert module_lines[8].strip() == "{{ label }}"
    assert template_lines[8].strip() == "{{ label }}"


def test_a_template_starting_on_the_opening_quote_line_is_aligned_too():
    source = 'class Tag:\n    x = 1\n    template = """<b>\n{{ label }}</b>"""\n'
    template = extract_template(source, "Tag")
    assert template.splitlines()[3] == "{{ label }}</b>"
    assert render(template, label="hi") == "<b>\nhi</b>"


def test_the_class_is_picked_by_name_when_a_module_holds_several():
    source = textwrap.dedent("""\
        class First:
            template = "<i>first</i>"


        class Second:
            template = "<i>second</i>"
        """)
    assert render(extract_template(source, "Second")) == "<i>second</i>"


def test_a_raw_string_keeps_its_backslashes():
    source = 'class Tag:\n    template = r"<script>/\\d+/</script>"\n'
    assert render(extract_template(source, "Tag")) == r"<script>/\d+/</script>"


def test_a_class_without_a_template_is_an_error_naming_the_class():
    with pytest.raises(ValueError, match="Badge.*no inline template"):
        extract_template("class Badge:\n    label = 1\n", "Badge")


def test_a_computed_template_is_an_error_pointing_at_its_line():
    source = 'class Tag:\n    name = "b"\n    template = f"<{name}/>"\n'
    with pytest.raises(ValueError, match="line 3.*plain string literal"):
        extract_template(source, "Tag")


@pytest.mark.parametrize(
    "value",
    ['"<b>" "</b>"', '(\n        "<b>"\n        "</b>"\n    )', '"""<b>\n""" r"</b>"'],
    ids=["one-line", "parenthesised", "mixed-quotes"],
)
def test_an_implicitly_concatenated_template_is_an_error(value):
    """Its pieces are joined before the line numbers could be counted."""
    source = f"class Tag:\n    template = {value}\n"
    with pytest.raises(ValueError, match=r"line \d.*plain string literal"):
        extract_template(source, "Tag")


def test_errors_name_the_module_file():
    with pytest.raises(ValueError, match=r"^/app/badge\.py, line 2: "):
        extract_template('class Tag:\n    template = f"{1}"\n', "Tag", "/app/badge.py")


def test_a_module_that_does_not_parse_reports_its_file():
    with pytest.raises(SyntaxError) as caught:
        extract_template("class Tag(:\n", "Tag", "/app/badge.py")
    assert caught.value.filename == "/app/badge.py"


def test_two_classes_with_one_name_are_ambiguous():
    source = textwrap.dedent("""\
        def first():
            class Tag:
                template = "<i>1</i>"


        def second():
            class Tag:
                template = "<i>2</i>"
        """)
    with pytest.raises(ValueError, match="lines 3, 8.*rename one"):
        extract_template(source, "Tag")


def test_an_annotated_class_variable_is_read_too():
    source = 'class Tag:\n    template: ClassVar[str] = "<b/>"\n'
    assert render(extract_template(source, "Tag")) == "<b/>"


def test_the_last_assignment_wins_as_it_does_in_python():
    source = 'class Tag:\n    template = "<i/>"\n    template = "<b/>"\n'
    assert render(extract_template(source, "Tag")) == "<b/>"


def test_a_pjx_document_is_its_files_text(tmp_path):
    path = tmp_path / "badge.pjx"
    path.write_text("<b>{{ label }}</b>")
    assert read_document(path, None) == "<b>{{ label }}</b>"


def test_an_inline_document_is_its_classs_extracted_template(tmp_path):
    path = tmp_path / "badge.py"
    path.write_text(BADGE)
    assert read_document(path, "Badge") == extract_template(BADGE, "Badge")


def test_an_inline_document_error_names_its_file(tmp_path):
    path = tmp_path / "badge.py"
    path.write_text(BADGE)
    with pytest.raises(ValueError, match=f"^{path}: class Nope"):
        read_document(path, "Nope")


SHELF = textwrap.dedent("""\
    from pyjinhx import BaseComponent


    class Tag(BaseComponent):
        template = "<i>tag</i>"


    class Pill(BaseComponent):
        template = "<b>pill</b>"
    """)


def test_a_module_is_parsed_once_for_all_the_templates_it_holds(monkeypatch):
    """Each class's template is read several times while it registers and
    renders, so a module of many components would otherwise be parsed that
    many times over."""
    import ast

    parses: list[str] = []
    real_parse = ast.parse

    def counting_parse(source, *args, **kwargs):
        parses.append(source)
        return real_parse(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse", counting_parse)
    filename = "shelf_parsed_once.py"

    for _ in range(3):
        assert extract_template(SHELF, "Tag", filename).endswith("<i>tag</i>")
        assert extract_template(SHELF, "Pill", filename).endswith("<b>pill</b>")

    assert len(parses) == 1


def test_an_edited_module_is_parsed_again():
    filename = "shelf_edited.py"
    extract_template(SHELF, "Tag", filename)

    edited = SHELF.replace("<i>tag</i>", "<i>edited</i>")

    assert extract_template(edited, "Tag", filename).endswith("<i>edited</i>")
    assert extract_template(SHELF, "Tag", filename).endswith("<i>tag</i>")


def shelf_of(count: int) -> str:
    classes = (
        f'class Tag{n}:\n    template = """\n    <i>{n}</i>\n    """\n'
        for n in range(count)
    )
    return "".join(classes)


def test_reading_every_template_of_a_module_splits_its_source_once():
    source = shelf_of(100)
    scanner._source_lines.cache_clear()

    for n in range(100):
        extract_template(source, f"Tag{n}", "/app/split_once.py")

    assert scanner._source_lines.cache_info().misses == 1


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_a_source_segment_matches_ast_for_non_ascii_multiline_nodes(newline):
    source = newline.join(['x = "é"; y = ("ü",', '     "ß")', "\x0czz = 1"])
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.expr):
            assert source_segment(source, node) == ast.get_source_segment(source, node)


# The stdlib-only half of reading a ``{#def#}`` signature.


def test_arguments_come_back_with_their_defaults():
    pairs = header_arguments('a: int, b: str = "x", c=pkg.mod.NAME, d=pkg.make()')

    assert [(arg.arg, default is not None) for arg, default in pairs] == [
        ("a", False),
        ("b", True),
        ("c", True),
        ("d", True),
    ]


@pytest.mark.parametrize(
    "signature",
    ["a, a", "*args", "**kw", "a, *, b", "a, /, b", "a=f(1)", "a=b", "a=pkg.f(x)"],
)
def test_what_a_header_may_not_hold_is_refused(signature):
    with pytest.raises(HeaderSignatureError) as refused:
        header_arguments(signature)

    assert refused.value.node is not None


def test_a_signature_that_does_not_parse_carries_the_syntax_error():
    with pytest.raises(HeaderSignatureError) as refused:
        header_arguments("a = 1, b")

    assert refused.value.syntax is not None


def test_an_unhashable_literal_default_is_refused_not_a_crash():
    with pytest.raises(HeaderSignatureError):
        header_arguments("f: int = {[1]: 2}")


@pytest.mark.parametrize(
    "header",
    ["f: int = {[1]: 2}", "f: Literal[{[1]: 2}] = 1"],
    ids=["default", "literal"],
)
def test_the_runtime_reports_an_unhashable_literal_as_a_value_error(header):
    from pyjinhx.components.props_header import parse_props_header

    with pytest.raises(ValueError):
        parse_props_header(f"{{#def {header} #}}\n<p></p>\n")


# The ``{#python ... #}`` block scanner: where a block is, and the Python
# source it yields with every line and column left where the file has it.


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
    block = scanner.python_block(SOURCE, "card.pjx")

    assert block is not None
    assert (block.open_line, block.close_line) == (1, 7)
    assert block.body.startswith("from pyjinhx import ReactiveComponent\n")
    assert block.body.endswith("    remaining: int = 0\n")


def test_no_block_is_none():
    assert scanner.python_block("<p>hi</p>", "card.pjx") is None
    assert scanner.python_source("<p>hi</p>", "card.pjx") is None


def test_the_source_puts_each_line_and_column_where_the_file_has_it():
    tree = ast.parse(scanner.python_source(SOURCE, "card.pjx") or "")

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

    tree = ast.parse(scanner.python_source(source, "card.pjx") or "")

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
    assert scanner.python_block(source, "card.pjx") is None


@pytest.mark.parametrize(
    ("source", "lineno", "code"),
    [
        ("{#python\nx = 1\n#}\n{#python\ny = 2\n#}", 4, scanner.SECOND_BLOCK),
        ('{#python\nx = "#}"\n#}', 2, scanner.PYTHON_BLOCK_EARLY_CLOSE),
        ('{#python\nx = f"{n:#}"\n#}', 2, scanner.PYTHON_BLOCK_EARLY_CLOSE),
        ("{#python\nx = 1  # done #}\n#}", 2, scanner.PYTHON_BLOCK_EARLY_CLOSE),
        ("{#python\nx = 1\n  #}", 3, scanner.CLOSER_NOT_AT_LINE_START),
        ("{#python\nx = 1\n-#}", 3, scanner.CLOSER_NOT_AT_LINE_START),
        ("{#python\nx = 1\n", 1, scanner.UNCLOSED_BLOCK),
        ("<p></p>\n{#python\n", 2, scanner.UNCLOSED_BLOCK),
        ("{#python\nx = 1\n#} <p></p>", 3, scanner.TEXT_AFTER_CLOSER),
    ],
)
def test_a_malformed_block_is_a_syntax_error_at_its_line(source, lineno, code):
    with pytest.raises(scanner.BlockSyntaxError) as raised:
        scanner.python_block(source, "card.pjx")

    assert raised.value.filename == "card.pjx"
    assert raised.value.lineno == lineno
    assert raised.value.code == code


def test_an_early_close_names_the_fix():
    with pytest.raises(SyntaxError, match=r'"#" "}"'):
        scanner.python_block('{#python\nx = "#}"\n#}', "card.pjx")


def test_a_body_line_that_is_only_the_closer_ends_the_block_there():
    block = scanner.python_block("{#python\nx = 1\n#}\ny = 2\n#}\n", "card.pjx")

    assert block is not None
    assert block.body == "x = 1\n"
    assert block.close_line == 3


def test_spaces_and_tabs_around_the_opener_and_closer_are_fine():
    block = scanner.python_block("{#python \t\nx = 1\n#}  \t\n", "card.pjx")

    assert block is not None
    assert block.body == "x = 1\n"


def test_crlf_line_endings_give_the_same_lines():
    source = SOURCE.replace("\n", "\r\n")

    block = scanner.python_block(source, "card.pjx")
    tree = ast.parse(scanner.python_source(source, "card.pjx") or "")

    assert block is not None
    assert (block.open_line, block.close_line) == (1, 7)
    assert next(n for n in tree.body if isinstance(n, ast.ClassDef)).lineno == 5


def test_an_empty_block_has_no_body_lines():
    block = scanner.python_block("{#python\n#}\n<p></p>", "card.pjx")

    assert block is not None
    assert block.body == ""
    assert block.close_line - block.open_line == 1


def test_a_closer_that_is_not_alone_says_so_rather_than_early_close():
    with pytest.raises(SyntaxError, match="alone in column 0"):
        scanner.python_block("{#python\nx = 1\n  #}", "card.pjx")


@pytest.mark.parametrize(
    "source",
    [
        "{% raw %}\n{#python\nx = 1\n#}\n{% endraw %}\n<p></p>",
        '{% set h = "{#" %}\n<p>{{ h }}</p>',
    ],
)
def test_jinja_raw_regions_and_tag_strings_hold_no_blocks(source):
    assert scanner.python_block(source, "card.pjx") is None


def test_a_closer_inside_a_tag_string_does_not_end_a_comment():
    source = '<p>{{ "#}" }}</p>\n{#python\nx = 1\n#}\n'

    block = scanner.python_block(source, "card.pjx")

    assert block is not None
    assert block.open_line == 2


def test_a_comment_opener_inside_a_tag_string_is_not_a_block():
    source = "{{ '\n{#python' }}\nx = 1\n#}\n"

    assert scanner.python_block(source, "card.pjx") is None


def test_read_document_drops_a_byte_order_mark(tmp_path):
    path = tmp_path / "card.pjx"
    path.write_bytes(b"\xef\xbb\xbf{#python\nx = 1\n#}\n<p></p>")

    block = scanner.python_block(scanner.read_document(path, None), "card.pjx")

    assert block is not None
    assert block.open_line == 1


def _seconds(scan, source: str) -> float:
    started = time.perf_counter()
    scan(source, "card.pjx")
    return time.perf_counter() - started


@pytest.mark.parametrize("opener", ["{{ ", "{% "])
def test_an_unclosed_tag_full_of_string_literals_scans_in_linear_time(opener):
    source = opener + '"a" ' * 40

    assert _seconds(scanner.python_block, source) < 1


@pytest.mark.parametrize("unit", ["{{ x\n", "{% raw %}\n", "{# x\n"])
def test_many_unclosed_openers_are_scanned_once(unit):
    assert _seconds(scanner.python_block, unit * 16000) < 1
    assert _seconds(lambda s, f: scanner.strip_to_text(s), unit * 16000) < 1


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
    assert scanner.opener_line(source) == line


def test_a_document_without_the_keyword_is_not_lexed(monkeypatch):
    class Unreadable:
        def finditer(self, source):
            raise AssertionError("lexed")

    monkeypatch.setattr(scanner, "_LEXEME_RE", Unreadable())

    assert scanner.opener_line("<p>{{ x }}</p>") is None
    assert scanner.python_block("<p>{# python #}</p>", "card.pjx") is None


def test_a_block_pads_its_body_to_the_files_own_lines():
    block = scanner.python_block("<p></p>\n{#python\nx = 1\n#}\n", "card.pjx")
    assert block is not None
    assert block.source == "\n\nx = 1\n"
    assert (
        scanner.python_source("<p></p>\n{#python\nx = 1\n#}\n", "card.pjx")
        == block.source
    )


def test_reworded_keeps_the_code_and_place_of_an_error():
    with pytest.raises(scanner.BlockSyntaxError) as raised:
        scanner.python_block("<p></p>\n{#python\nx = 1\n", "card.pjx")
    error = scanner.reworded(raised.value, "other.pjx", "said again")
    assert (error.code, error.msg, error.filename) == (
        scanner.UNCLOSED_BLOCK,
        "said again",
        "other.pjx",
    )
    assert (error.lineno, error.offset) == (raised.value.lineno, raised.value.offset)


def test_normalize_text_drops_the_mark_and_counts_every_line_break_once():
    assert scanner.normalize_text("\ufeffa\r\nb\rc\n") == "a\nb\nc\n"


def test_blank_comments_keeps_the_lines():
    assert scanner.blank_comments("a{#x\ny#}b\n{{ 1 }}") == "a\nb\n{{ 1 }}"


def test_package_root_is_the_highest_directory_of_the_chain(tmp_path):
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    for name in ("a", "a/b", "a/b/c"):
        (tmp_path / name / "__init__.py").write_text("")
    assert scanner.package_root(tmp_path / "a" / "b" / "c") == tmp_path / "a"
    assert scanner.package_root(tmp_path) is None
