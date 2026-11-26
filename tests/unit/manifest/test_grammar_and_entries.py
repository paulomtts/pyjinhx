"""Tests for the manifest grammar and the entries it lists for each kind of component."""

import json
import sys
from pathlib import Path

import pytest

from pyjinhx import manifest
from pyjinhx.document import scanner
from tests.unit.manifest._helpers import _abs, _at, _components, _grammar, _write


def test_the_grammar_ships_as_package_data():
    grammar = _grammar()

    assert grammar["version"] == 1


def test_grammar_flag_prints_the_data_file(capsys):
    assert manifest.main(["--grammar"]) == 0

    assert json.loads(capsys.readouterr().out) == _grammar()


def test_the_grammar_names_exactly_the_keywords_the_scanners_accept():
    assert set(_grammar()["keywords"]) == set(scanner.BLOCK_KEYWORDS)


def test_the_grammar_lists_exactly_the_error_codes_the_scanners_raise():
    assert set(_grammar()["error_codes"]) == {
        scanner.PYTHON_BLOCK_EARLY_CLOSE,
        scanner.SECOND_BLOCK,
        scanner.CLOSER_NOT_AT_LINE_START,
        scanner.UNCLOSED_BLOCK,
        scanner.TEXT_AFTER_CLOSER,
        scanner.STRAY_COMMENT_CLOSE,
    }


@pytest.mark.parametrize("keyword", scanner.BLOCK_KEYWORDS)
def test_each_keyword_follows_the_rule_the_grammar_states(keyword):
    rules = _grammar()["keywords"][keyword]
    one_line = f"{{#{keyword} x #}}\n<p></p>\n"
    spaced = f"{{# {keyword}\nx\n#}}\n<p></p>\n"
    controlled = f"{{#-{keyword}\nx\n#}}\n<p></p>\n"

    def found(source: str) -> bool:
        blocks, _ = manifest.scan_blocks(source, "t.pjx")
        return any(b["keyword"] == keyword for b in blocks)

    assert found(one_line) is (rules["after_keyword"] == "whitespace_or_end")
    assert not found(spaced)
    assert not found(controlled)


def test_the_manifest_lists_one_component_of_each_kind(tree):
    found = _components(tree)

    assert {tag: c["kind"] for tag, c in found.items()} == {
        "Badge": "template",
        "TodoCount": "pjx-python",
        "Chip": "py-template",
        "Tag": "py-template",
        "Card": "split",
    }
    assert found["TodoCount"]["document"]["path"] == _abs("app/ui/todo_count.pjx")
    assert found["Chip"]["document"]["path"] == _abs("app/ui/chip.py")
    assert found["Card"]["document"]["path"] == _abs("app/ui/card.pjx")
    assert found["Card"]["class"]["path"] == _abs("app/ui/card.py")
    assert found["Card"]["class"]["module"] == "app.ui.card"
    assert found["Badge"]["class"] is None


def test_the_top_level_names_the_manifest_and_grammar_versions_and_roots(tree):
    result = manifest.describe([Path("app")])

    assert result["manifest_version"] == 1
    assert result["grammar_version"] == _grammar()["version"]
    assert result["roots"] == [_abs("app")]
    assert isinstance(result["pyjinhx_version"], str)


def test_a_pjx_python_component_has_its_blocks_class_props_and_members(tree):
    found = _components(tree)["TodoCount"]

    assert found["document"]["markup_lines"] == [25, 25]
    assert found["blocks"] == [
        {"keyword": "python", "open_line": 1, "body_lines": [2, 23], "close_line": 24},
        {"keyword": "css", "open_line": 26, "body_lines": [27, 27], "close_line": 28},
    ]
    assert found["class"] == {
        "module": "app.ui.todo_count",
        "qualname": "TodoCount",
        "path": _abs("app/ui/todo_count.pjx"),
        "range": {
            "start": {"line": 5, "column": 6},
            "end": {"line": 5, "column": 15},
        },
        "bases": ["ReactiveComponent"],
        "stub": None,
    }
    assert [(m["name"], m["kind"], _at(m)) for m in found["members"]] == [
        ("done", "property", (15, 8)),
        ("describe", "method", (18, 8)),
        ("load", "classmethod", (22, 8)),
    ]
    assert found["members"][0]["range"]["end"] == {"line": 15, "column": 12}


def test_props_carry_source_text_flags_and_positions(tree):
    props = {p["name"]: p for p in _components(tree)["TodoCount"]["props"]}

    assert list(props) == ["remaining", "mode", "title", "items", "body", "label"]
    assert props["remaining"] == {
        "name": "remaining",
        "annotation": "int",
        "required": False,
        "default": "0",
        "literal_values": None,
        "slot": False,
        "children": False,
        "range": {
            "start": {"line": 6, "column": 4},
            "end": {"line": 6, "column": 13},
        },
    }
    assert props["mode"]["literal_values"] == ["a", "b"]
    assert props["mode"]["annotation"] == 'Literal["a", "b"]'
    assert [props[n]["slot"] for n in ("title", "items", "body")] == [True, True, False]
    assert props["title"]["annotation"] == "Slot | None"
    assert props["body"]["children"] is True
    assert props["items"]["required"] is True
    assert props["items"]["default"] is None
    assert props["label"]["required"] is True


def test_the_stub_is_the_adjacent_path_when_it_exists(tree):
    (tree / "app/ui/todo_count.pyi").write_text("# stub\n")

    assert _components(tree)["TodoCount"]["class"]["stub"] == _abs(
        "app/ui/todo_count.pyi"
    )


def test_a_template_component_gets_its_props_from_the_header_unresolved(tree):
    before = set(sys.modules)

    found = _components(tree)["Badge"]
    props = {p["name"]: p for p in found["props"]}

    assert set(sys.modules) == before
    assert list(props) == ["label", "when", "tone", "size"]
    assert props["label"]["required"] is True
    assert props["tone"]["literal_values"] == ["info", "warn"]
    assert props["when"]["annotation"] == "datetime.datetime"
    assert props["size"]["annotation"] == "nowhere.mod.Size"
    assert props["size"]["default"] == "nowhere.mod.DEFAULT"
    assert _at(props["label"]) == (1, 6)
    assert _at(props["size"]) == (2, 46)
    assert found["blocks"] == [{"keyword": "def", "open_line": 1, "close_line": 2}]
    assert found["document"]["markup_lines"] == [3, 3]


def test_a_py_template_component_has_the_literals_span_and_two_share_a_module(tree):
    found = _components(tree)

    chip, tag = found["Chip"], found["Tag"]
    assert chip["class"]["module"] == "app.ui.chip"
    assert _at(chip["class"]) == (4, 6)
    assert chip["document"]["markup_lines"] == [7, 9]
    assert chip["document"]["span"] == {
        "start": {"line": 7, "column": 18},
        "end": {"line": 9, "column": 4},
    }
    assert [p["name"] for p in chip["props"]] == ["label"]
    assert tag["document"]["markup_lines"] == [13, 13]
    assert "Helper" not in found


def test_a_split_component_reads_its_class_from_the_py_and_blocks_from_the_pjx(tree):
    found = _components(tree)["Card"]

    assert [p["name"] for p in found["props"]] == ["title"]
    assert found["document"]["markup_lines"] == [1, 1]
    assert _at(found["class"]) == (4, 6)


def test_a_subclass_without_a_template_of_its_own_is_not_listed(tree):
    (tree / "app/ui/wide_card.py").write_text(
        "from app.ui.card import Card\n\n\nclass WideCard(Card):\n    pass\n"
    )

    assert "WideCard" not in _components(tree)


def test_a_subclass_in_the_same_block_is_listed_with_the_documents_markup(tree):
    (tree / "app/ui/card.pjx").unlink()
    (tree / "app/ui/card.py").unlink()
    (tree / "app/ui/card.pjx").write_text(
        "{#python\nclass Card:\n    title: str\n\n\n"
        "class WideCard(Card):\n    width: int = 2\n\n\n"
        "class Wider(WideCard):\n    pass\n\n\nclass Helper:\n    pass\n#}\n"
        "<p>{{ title }}</p>\n"
    )

    found = _components(tree)

    assert {"Card", "WideCard", "Wider"} <= set(found)
    assert "Helper" not in found
    wide = found["WideCard"]
    assert wide["kind"] == "pjx-python"
    assert wide["document"] == found["Card"]["document"]
    assert wide["class"]["bases"] == ["Card"]
    assert [p["name"] for p in wide["props"]] == ["width"]
    assert _at(wide["class"]) == (6, 6)


def test_a_class_in_a_block_owns_the_sibling_document_named_for_it(tree):
    _write(
        tree,
        {
            # "widget_part" sorts after "widget", and "a_part" before it
            "app/ui/widget.pjx": "{#python\nfrom pyjinhx import BaseComponent\n\n\n"
            "class Widget(BaseComponent):\n    pass\n\n\n"
            "class WidgetPart(BaseComponent):\n    label: str\n\n\n"
            "class APart(BaseComponent):\n    size: int = 1\n#}\n<p></p>\n",
            "app/ui/widget_part.pjx": "<b>{{ label }}</b>\n",
            "app/ui/a_part.pjx": "<i>{{ size }}</i>\n",
        },
    )

    result = manifest.describe([Path("app")])
    parts = [c for c in result["components"] if c["tag"] in ("WidgetPart", "APart")]

    assert sorted((c["tag"], c["kind"]) for c in parts) == [
        ("APart", "pjx-python"),
        ("WidgetPart", "pjx-python"),
    ]
    part = next(c for c in parts if c["tag"] == "WidgetPart")
    assert part["document"]["path"] == _abs("app/ui/widget_part.pjx")
    assert part["class"]["path"] == _abs("app/ui/widget.pjx")
    assert [p["name"] for p in part["props"]] == ["label"]
    assert part["document"]["markup_lines"] == [1, 1]


def test_columns_are_utf16_code_units(tree):
    (tree / "app/ui/emoji.pjx").write_text(
        "{#python\nclass Emoji:\n    a: int = 1; b: str = '😀'; c: int\n#}\n<p></p>\n",
        encoding="utf-8",
    )

    props = {p["name"]: p for p in _components(tree)["Emoji"]["props"]}

    # The emoji is one character but two UTF-16 code units, and four UTF-8 bytes.
    assert _at(props["c"])[1] == len("    a: int = 1; b: str = '😀'; ") + 1
