"""The manifest: what an editor learns about components without running them."""

import json
import sys
from importlib import resources
from pathlib import Path

import pytest

from pyjinhx import manifest, sfc


def _grammar() -> dict:
    text = resources.files("pyjinhx").joinpath("block_grammar.json").read_text("utf-8")
    return json.loads(text)


def test_the_grammar_ships_as_package_data():
    grammar = _grammar()

    assert grammar["version"] == 1


def test_grammar_flag_prints_the_data_file(capsys):
    assert manifest.main(["--grammar"]) == 0

    assert json.loads(capsys.readouterr().out) == _grammar()


def test_the_grammar_names_exactly_the_keywords_the_scanners_accept():
    assert set(_grammar()["keywords"]) == set(sfc.BLOCK_KEYWORDS)


def test_the_grammar_lists_exactly_the_error_codes_the_scanners_raise():
    assert set(_grammar()["error_codes"]) == {
        sfc.PYTHON_BLOCK_EARLY_CLOSE,
        sfc.SECOND_BLOCK,
        sfc.OPENER_NOT_AT_LINE_START,
        sfc.CLOSER_NOT_AT_LINE_START,
        sfc.UNCLOSED_BLOCK,
        sfc.TEXT_AFTER_CLOSER,
        sfc.STRAY_COMMENT_CLOSE,
    }


@pytest.mark.parametrize("keyword", sfc.BLOCK_KEYWORDS)
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


BADGE = """\
{#def label: str, when: datetime.datetime,
      tone: Literal["info", "warn"] = "info", size: nowhere.mod.Size = nowhere.mod.DEFAULT #}
<span>{{ label }}</span>
"""

TODO_COUNT = """\
{#python
from pyjinhx import ReactiveComponent, Slot, Children


class TodoCount(ReactiveComponent):
    remaining: int = 0
    mode: Literal["a", "b"] = "a"
    title: Slot | None = None
    items: list[Slot]
    body: Children
    label: str = ...
    _private: int = 0

    @property
    def done(self) -> bool:
        return not self.remaining

    def describe(self):
        return "x"

    @classmethod
    def load(cls):
        return cls()
#}
<div>{{ remaining }}</div>
{#css
.count { color: red; }
#}
"""

CHIP = '''\
from pyjinhx import BaseComponent


class Chip(BaseComponent):
    label: str

    template = """
    <b>{{ label }}</b>
    """


class Tag(BaseComponent):
    template = "<i></i>"


class Helper:
    pass
'''

CARD_PY = """\
from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str
"""


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A project of one component of each kind, with the cwd at its root."""
    _write(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/ui/__init__.py": "",
            "app/ui/badge.pjx": BADGE,
            "app/ui/todo_count.pjx": TODO_COUNT,
            "app/ui/chip.py": CHIP,
            "app/ui/card.py": CARD_PY,
            "app/ui/card.pjx": "<p>{{ title }}</p>\n",
        },
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _components(tree) -> dict[str, dict]:
    result = manifest.describe([Path("app")])
    return {c["tag"]: c for c in result["components"]}


def test_the_manifest_lists_one_component_of_each_kind(tree):
    found = _components(tree)

    assert {tag: c["kind"] for tag, c in found.items()} == {
        "Badge": "template",
        "TodoCount": "pjx-python",
        "Chip": "py-template",
        "Tag": "py-template",
        "Card": "split",
    }
    assert found["TodoCount"]["document"]["path"] == "app/ui/todo_count.pjx"
    assert found["Chip"]["document"]["path"] == "app/ui/chip.py"
    assert found["Card"]["document"]["path"] == "app/ui/card.pjx"
    assert found["Card"]["class"]["path"] == "app/ui/card.py"
    assert found["Card"]["class"]["module"] == "app.ui.card"
    assert found["Badge"]["class"] is None


def test_the_top_level_names_the_manifest_and_grammar_versions_and_roots(tree):
    result = manifest.describe([Path("app")])

    assert result["manifest_version"] == 1
    assert result["grammar_version"] == _grammar()["version"]
    assert result["roots"] == ["app"]
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
        "path": "app/ui/todo_count.pjx",
        "line": 5,
        "column": 6,
        "bases": ["ReactiveComponent"],
        "stub": None,
    }
    assert found["members"] == [
        {"name": "done", "kind": "property", "line": 15, "column": 8},
        {"name": "describe", "kind": "method", "line": 18, "column": 8},
        {"name": "load", "kind": "classmethod", "line": 22, "column": 8},
    ]


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
        "line": 6,
        "column": 4,
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

    assert _components(tree)["TodoCount"]["class"]["stub"] == "app/ui/todo_count.pyi"


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
    assert (props["label"]["line"], props["label"]["column"]) == (1, 6)
    assert (props["size"]["line"], props["size"]["column"]) == (2, 46)
    assert found["blocks"] == [{"keyword": "def", "open_line": 1, "close_line": 2}]
    assert found["document"]["markup_lines"] == [3, 3]


def test_a_py_template_component_has_the_literals_span_and_two_share_a_module(tree):
    found = _components(tree)

    chip, tag = found["Chip"], found["Tag"]
    assert chip["class"]["module"] == "app.ui.chip"
    assert (chip["class"]["line"], chip["class"]["column"]) == (4, 6)
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
    assert found["class"]["line"] == 4


def test_a_subclass_without_a_template_of_its_own_is_not_listed(tree):
    (tree / "app/ui/wide_card.py").write_text(
        "from app.ui.card import Card\n\n\nclass WideCard(Card):\n    pass\n"
    )

    assert "WideCard" not in _components(tree)


def test_columns_are_utf16_code_units(tree):
    (tree / "app/ui/emoji.pjx").write_text(
        "{#python\nclass Emoji:\n    a: int = 1; b: str = '😀'; c: int\n#}\n<p></p>\n",
        encoding="utf-8",
    )

    props = {p["name"]: p for p in _components(tree)["Emoji"]["props"]}

    # The emoji is one character but two UTF-16 code units, and four UTF-8 bytes.
    assert props["c"]["column"] == len("    a: int = 1; b: str = '😀'; ") + 1
