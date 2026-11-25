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


def _abs(relative: str) -> str:
    """The absolute POSIX path of ``relative`` under the working directory."""
    return (Path.cwd() / relative).as_posix()


def _at(entry: dict) -> tuple[int, int]:
    """The line and column where an entry's range starts."""
    start = entry["range"]["start"]
    return start["line"], start["column"]


def _components(tree) -> dict[str, dict]:
    result = manifest.describe([Path("app")])
    return {c["tag"]: c for c in result["components"] if not c["builtin"]}


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


def test_columns_are_utf16_code_units(tree):
    (tree / "app/ui/emoji.pjx").write_text(
        "{#python\nclass Emoji:\n    a: int = 1; b: str = '😀'; c: int\n#}\n<p></p>\n",
        encoding="utf-8",
    )

    props = {p["name"]: p for p in _components(tree)["Emoji"]["props"]}

    # The emoji is one character but two UTF-16 code units, and four UTF-8 bytes.
    assert _at(props["c"])[1] == len("    a: int = 1; b: str = '😀'; ") + 1


CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "block_grammar"


def _diagnostics(root: Path, *where: str) -> list[dict]:
    return manifest.describe([Path(w) for w in where] or [Path(".")])["diagnostics"]


def _one(diagnostics: list[dict], code: str) -> dict:
    found = [d for d in diagnostics if d["code"] == code]
    assert len(found) == 1, diagnostics
    return found[0]


def _error_cases() -> list:
    cases = []
    for case in sorted(CORPUS.glob("*.pjx")):
        expected = json.loads(case.with_suffix(".json").read_text(encoding="utf-8"))
        if expected["error"] and "known_gap" not in expected:
            cases.append(pytest.param(case, expected["error"], id=case.stem))
    return cases


@pytest.mark.parametrize(("case", "error"), _error_cases())
def test_every_grammar_error_is_a_diagnostic_with_its_code_and_line(
    tmp_path, monkeypatch, case, error
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_bytes(case.read_bytes())

    found = _diagnostics(tmp_path)

    assert (_abs("card.pjx"), error["code"], error["line"]) in [
        (d["path"], d["code"], _at(d)[0]) for d in found
    ]
    assert {d["severity"] for d in found if d["code"] == error["code"]} == {"error"}


def test_a_grammar_diagnostic_has_a_utf16_column(tree):
    (tree / "app/ui/early.pjx").write_text(
        '{#python\nx = "😀" + "#}"\n#}\n<p></p>\n', encoding="utf-8"
    )

    found = _one(_diagnostics(tree, "app"), "python-block-early-close")

    # `x = "😀" + "` is 11 characters and 12 UTF-16 code units.
    assert _at(found) == (2, 12)


def _document(tree, text: str, name: str = "card.pjx") -> list[dict]:
    (tree / name).write_text(text, encoding="utf-8")
    return manifest.describe([Path(name)])["diagnostics"]


GOOD = "{#python\nclass Card:\n    title: str\n#}\n<p>{{ title }}</p>\n"


def test_a_python_syntax_error_in_a_block_is_reported_at_the_files_line(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(tmp_path, "{#python\nclass Card:\n    x = = 1\n#}\n<p></p>\n"),
        "python-syntax-error",
    )

    assert (_at(found), found["severity"]) == ((3, 8), "error")


def test_def_with_python_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    found = _one(_document(tmp_path, "{#def title: str #}\n" + GOOD), "def-with-python")

    assert (_at(found), found["severity"]) == ((1, 0), "error")


def test_no_class_named_for_the_file_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(tmp_path, GOOD.replace("Card", "Other")), "no-component-class"
    )

    assert (_at(found), found["severity"]) == ((1, 0), "error")


def test_two_classes_that_snake_to_the_stem_are_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(
            tmp_path,
            "{#python\nclass HTTPCard:\n    pass\n\n\nclass HttpCard:\n    pass\n#}\n<p></p>\n",
            "http_card.pjx",
        ),
        "ambiguous-component-class",
    )

    assert _at(found)[0] == 6


def test_a_class_in_a_block_that_assigns_template_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(tmp_path, GOOD.replace("title: str", 'template = "<p></p>"')),
        "template-in-block",
    )

    assert _at(found)[0] == 3


def test_a_block_with_no_markup_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(tmp_path, "{#python\nclass Card:\n    pass\n#}\n{# note #}\n\n"),
        "no-markup",
    )

    assert (_at(found), found["severity"]) == ((1, 0), "error")


def test_a_module_beside_a_block_shadows_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.py").write_text("")

    found = _one(_document(tmp_path, GOOD), "shadowed-by-module")

    assert (_at(found), found["severity"]) == ((1, 0), "error")


def test_a_package_beside_a_block_shadows_it_too(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card").mkdir()

    assert _one(_document(tmp_path, GOOD), "shadowed-by-module")


def test_a_template_that_is_not_one_plain_literal_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "chip.py").write_text(
        'class Chip:\n    template = "<a>" + "</a>"\n', encoding="utf-8"
    )

    found = _one(
        manifest.describe([Path("chip.py")])["diagnostics"], "template-not-literal"
    )

    assert (found["path"], _at(found)) == (_abs("chip.py"), (2, 15))


def test_a_malformed_header_is_a_diagnostic_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(tmp_path, "{#def a = 1, b #}\n<p></p>\n"), "def-header-invalid"
    )

    assert found["severity"] == "error"


def test_a_file_with_a_diagnostic_still_has_its_entry_when_one_can_be_built(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.py").write_text("")
    (tmp_path / "card.pjx").write_text(GOOD)
    (tmp_path / "broken.pjx").write_text(
        "{#python\nclass Broken:\n    x = = 1\n#}\n<p></p>\n"
    )
    (tmp_path / "other.pjx").write_text(
        "{#python\nclass Nope:\n    pass\n#}\n<p></p>\n"
    )

    result = manifest.describe([Path(".")])

    entries = {c["tag"]: c for c in result["components"]}
    assert _at(entries["Card"]["class"]) == (2, 6)
    assert entries["Broken"]["class"] is None
    assert entries["Other"]["class"] is None


def test_a_missing_stale_hand_written_and_orphaned_stub_are_warnings(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text(GOOD)

    missing = _one(manifest.describe([Path(".")])["diagnostics"], "stub-missing")
    assert (missing["path"], _at(missing), missing["severity"]) == (
        _abs("card.pjx"),
        (1, 0),
        "warning",
    )

    (tmp_path / "card.pyi").write_text(
        "# pyjinhx.stubgen: generated from card.pjx; do not edit\n"
    )
    assert _one(manifest.describe([Path(".")])["diagnostics"], "stub-stale")[
        "path"
    ] == _abs("card.pjx")

    (tmp_path / "card.pyi").write_text("class Card: ...\n")
    assert _one(manifest.describe([Path(".")])["diagnostics"], "stub-handwritten")

    (tmp_path / "card.pjx").unlink()
    (tmp_path / "card.pyi").write_text(
        "# pyjinhx.stubgen: generated from card.pjx; do not edit\n"
    )
    orphan = _one(manifest.describe([Path(".")])["diagnostics"], "stub-orphaned")
    assert orphan["path"] == _abs("card.pyi")


def test_a_fresh_stub_raises_no_diagnostic(tmp_path, monkeypatch):
    from pyjinhx import stubgen

    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text(GOOD)
    stubgen.main(["."])

    assert manifest.describe([Path(".")])["diagnostics"] == []


def test_a_block_that_would_write_a_sentinel_is_never_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sentinel = tmp_path / "ran"
    (tmp_path / "card.pjx").write_text(
        f"{{#python\nopen({str(sentinel)!r}, 'w').close()\n\n\nclass Card:\n    pass\n#}}\n<p></p>\n"
    )
    (tmp_path / "chip.py").write_text(
        f"open({str(sentinel)!r}, 'w').close()\n\n\nclass Chip:\n    template = '<p></p>'\n"
    )

    manifest.describe([Path(".")])
    manifest.describe_buffer(Path("card.pjx"), (tmp_path / "card.pjx").read_text())

    assert not sentinel.exists()


def test_the_output_is_sorted_and_the_same_every_time(tree):
    first = json.dumps(manifest.describe([Path("app")]))
    second = json.dumps(manifest.describe([Path("app")]))

    result = json.loads(first)
    keys = [
        (c["document"]["path"], _at(c["class"])[0] if c["class"] else 0)
        for c in result["components"]
    ]
    assert first == second
    assert keys == sorted(keys)


def test_module_names_follow_the_init_files(tmp_path):
    (tmp_path / "pkg" / "sub").mkdir(parents=True)
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "sub" / "__init__.py").write_text("")
    (tmp_path / "loose").mkdir()

    assert sfc.module_name_for(tmp_path / "pkg/sub/card.pjx") == "pkg.sub.card"
    assert sfc.module_name_for(tmp_path / "pkg/sub/__init__.py") == "pkg.sub"
    assert sfc.module_name_for(tmp_path / "loose/card.pjx") == "card"
    assert sfc.module_name_for(tmp_path / "pkg/not_yet/card.pjx") == "card"


def _stdin(monkeypatch, text: str) -> None:
    import io

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(text.encode())))


def test_stdin_describes_the_piped_text_and_not_the_file_on_disk(
    tree, monkeypatch, capsys
):
    _stdin(monkeypatch, GOOD.replace("Card", "Fresh"))
    (tree / "app/ui/fresh.pjx").write_text("<p>on disk</p>\n")

    assert manifest.main(["--stdin", "--filename", "app/ui/fresh.pjx"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert [c["tag"] for c in result["components"]] == ["Fresh"]
    assert result["components"][0]["kind"] == "pjx-python"
    assert result["diagnostics"] == []


def test_stdin_for_a_file_that_does_not_exist_reports_no_stub_diagnostics(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    _stdin(monkeypatch, GOOD)

    assert manifest.main(["--stdin", "--filename", "new/card.pjx"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert [c["tag"] for c in result["components"]] == ["Card"]
    assert result["diagnostics"] == []


def test_stdin_reports_the_buffers_errors_only(tree, monkeypatch, capsys):
    _stdin(monkeypatch, "{#python\nclass Card:\n    x = = 1\n#}\n<p></p>\n")

    manifest.main(["--stdin", "--filename", "app/ui/todo_count.pjx"])

    result = json.loads(capsys.readouterr().out)
    assert {d["path"] for d in result["diagnostics"]} == {_abs("app/ui/todo_count.pjx")}
    assert result["diagnostics"][0]["code"] == "python-syntax-error"


def test_stdin_of_a_py_buffer_sees_its_pjx_neighbour(tree, monkeypatch, capsys):
    _stdin(monkeypatch, CARD_PY.replace("title: str", "title: str\n    size: int = 1"))

    manifest.main(["--stdin", "--filename", "app/ui/card.py"])

    result = json.loads(capsys.readouterr().out)
    assert [c["kind"] for c in result["components"]] == ["split"]
    assert [p["name"] for p in result["components"][0]["props"]] == ["title", "size"]


def test_stdin_needs_a_filename(capsys):
    with pytest.raises(SystemExit) as exit_:
        manifest.main(["--stdin"])

    assert exit_.value.code == 2


def test_a_path_that_does_not_exist_exits_2(tmp_path, capsys):
    assert manifest.main([str(tmp_path / "nope")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_the_command_runs_without_importing_pydantic(tree):
    import subprocess

    code = (
        "import sys; from pyjinhx import manifest; "
        "manifest.main(['app']); "
        "assert 'pydantic' not in sys.modules, 'pydantic'; "
        "assert 'app.ui.todo_count' not in sys.modules"
    )
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=tree,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["manifest_version"] == 1


def test_python_dash_m_prints_the_grammar():
    import subprocess

    done = subprocess.run(
        [sys.executable, "-m", "pyjinhx.manifest", "--grammar"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert json.loads(done.stdout) == _grammar()


def test_a_legacy_spaced_header_beside_a_block_is_refused_too(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(tmp_path, "{# def title: str #}\n" + GOOD), "def-with-python"
    )

    assert found["range"] == {
        "start": {"line": 1, "column": 0},
        "end": {"line": 1, "column": 20},
    }


def test_a_class_beside_a_document_that_holds_its_own_class_is_refused(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text(GOOD)
    (tmp_path / "widgets.py").write_text("class Card:\n    pass\n")

    found = _one(
        manifest.describe([Path(".")])["diagnostics"], "class-outside-document"
    )

    assert (found["path"], _at(found), found["severity"]) == (
        _abs("widgets.py"),
        (1, 6),
        "error",
    )


@pytest.mark.parametrize(
    ("signature", "where"),
    [
        ("a: int, a: str", (1, 14)),
        ("*args", (1, 7)),
        ("a, *, b", (1, 12)),
        ("a, **kw", (1, 11)),
        ("a=make(1)", (1, 8)),
        ("a: int = 1,\n      b=other", (2, 8)),
        ("a = 1, b", (1, 13)),
    ],
)
def test_a_header_the_runtime_refuses_is_reported_where_it_goes_wrong(
    tmp_path, monkeypatch, signature, where
):
    monkeypatch.chdir(tmp_path)

    found = _one(
        _document(tmp_path, f"{{#def {signature} #}}\n<p></p>\n"), "def-header-invalid"
    )

    assert found["severity"] == "error"
    assert _at(found) == where
    assert found["range"]["end"] != found["range"]["start"] or signature == "a = 1, b"


def test_every_component_has_a_name_an_id_and_a_replaces_flag(tree):
    (tree / "app/ui/swap.py").write_text(
        "class Swap(BaseComponent, pjx_replace=True):\n    template = '<p></p>'\n"
    )
    found = _components(tree)

    assert found["TodoCount"]["name"] == "todo_count"
    assert found["TodoCount"]["id"] == _abs("app/ui/todo_count.pjx") + "#TodoCount"
    assert found["Badge"]["id"] == _abs("app/ui/badge.pjx")
    assert found["Chip"]["id"] == _abs("app/ui/chip.py") + "#Chip"
    assert found["Card"]["id"] == _abs("app/ui/card.py") + "#Card"
    assert found["Swap"]["replaces"] is True
    assert found["Chip"]["replaces"] is False


def test_the_ids_of_a_tree_are_unique(tree):
    result = manifest.describe([Path("app")])

    ids = [c["id"] for c in result["components"]]
    assert len(ids) == len(set(ids))


def _collisions(tree, **files: str) -> list[dict]:
    _write(tree, {f"app/ui/{name}.py": text for name, text in files.items()})
    result = manifest.describe([Path("app")])
    return [d for d in result["diagnostics"] if d["code"] == "tag-collision"]


def test_two_components_with_one_name_are_a_warning_on_each(tree):
    found = _collisions(
        tree,
        other="class Chip:\n    template = '<i></i>'\n",
    )

    assert {(d["path"], d["severity"]) for d in found} == {
        (_abs("app/ui/chip.py"), "warning"),
        (_abs("app/ui/other.py"), "warning"),
    }


def test_one_component_that_replaces_settles_a_collision(tree):
    found = _collisions(
        tree,
        other="class Chip(pjx_replace=True):\n    template = '<i></i>'\n",
    )

    assert found == []


def test_the_builtins_are_listed_and_marked(tree):
    result = manifest.describe([Path("app")])

    builtins = [c for c in result["components"] if c["builtin"]]
    assert any(c["tag"] == "PJXBadge" for c in builtins)
    assert all(not c["builtin"] for c in result["components"] if c["tag"] == "Chip")
    assert result["diagnostics"] == [
        d for d in result["diagnostics"] if d["code"].startswith("stub-")
    ]


def test_scanning_the_package_does_not_list_a_builtin_twice(monkeypatch):
    root = Path(manifest.__file__).parent
    monkeypatch.chdir(root.parent)

    result = manifest.describe([root])

    ids = [c["id"] for c in result["components"]]
    assert len(ids) == len(set(ids))
    assert any(c["builtin"] for c in result["components"])


def test_a_package_layout_names_modules_by_the_deepest_sys_path_entry(tmp_path):
    (tmp_path / "src" / "ns" / "ui").mkdir(parents=True)
    path = tmp_path / "src" / "ns" / "ui" / "card.pjx"

    assert sfc.module_name_for(path) == "card"
    assert sfc.module_name_for(path, [str(tmp_path / "src")]) == "ns.ui.card"
    assert (
        sfc.module_name_for(path, [str(tmp_path / "src"), str(tmp_path / "src" / "ns")])
        == "ui.card"
    )
    assert sfc.module_name_for(path, [str(tmp_path / "other")]) is None


def test_sys_path_names_the_class_module_in_the_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"src/ns/card.pjx": GOOD})

    manifest.main(["--sys-path", "src", "src"])

    components = json.loads(capsys.readouterr().out)["components"]
    card = next(c for c in components if not c["builtin"])
    assert card["class"]["module"] == "ns.card"


def test_a_split_component_knows_when_its_document_has_a_stale_header(tree):
    (tree / "app/ui/card.pjx").write_text("{#def title: str #}\n<p></p>\n")

    found = _components(tree)

    assert found["Card"]["has_stale_def_header"] is True
    assert found["Chip"]["has_stale_def_header"] is False


def test_strict_is_read_from_the_class_body_and_null_when_not_stated(tree):
    _write(
        tree,
        {
            "app/ui/loose.py": "class Loose:\n"
            "    model_config = ConfigDict(extra='allow')\n"
            "    template = '<p></p>'\n",
            "app/ui/tight.py": "class Tight:\n"
            "    model_config = {'extra': 'forbid'}\n"
            "    template = '<p></p>'\n",
        },
    )

    found = _components(tree)

    assert (found["Loose"]["strict"], found["Tight"]["strict"]) == (False, True)
    assert found["Chip"]["strict"] is None
    assert found["Badge"]["strict"] is False


def test_sibling_assets_are_listed_when_they_exist(tree):
    (tree / "app/ui/chip.css").write_text("")
    (tree / "app/ui/todo_count.js").write_text("")

    found = _components(tree)

    assert found["Chip"]["assets"] == {"css": _abs("app/ui/chip.css"), "js": None}
    assert found["TodoCount"]["assets"] == {
        "css": None,
        "js": _abs("app/ui/todo_count.js"),
    }


def test_a_document_with_a_python_block_that_does_not_scan_still_has_an_entry(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text("{#python\nclass Card:\n    pass\n<p></p>\n")

    result = manifest.describe([Path(".")])

    mine = [c for c in result["components"] if not c["builtin"]]
    assert [(c["tag"], c["kind"], c["class"]) for c in mine] == [
        ("Card", "pjx-python", None)
    ]
    assert [d["code"] for d in result["diagnostics"]] == ["unclosed-block"]


def test_a_spaced_opener_and_prose_are_templates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text("{#python is nice #}\n<p></p>\n")
    (tmp_path / "chip.pjx").write_text("{# python\nclass Chip: pass\n#}\n<p></p>\n")

    result = manifest.describe([Path(".")])

    mine = {c["tag"]: c for c in result["components"] if not c["builtin"]}
    assert mine["Card"]["kind"] == "template"
    assert mine["Chip"]["kind"] == "template"
    diagnostics = {
        Path(d["path"]).name: d
        for d in result["diagnostics"]
        if d["path"].endswith(".pjx")
    }
    assert diagnostics == {}


def test_an_indented_python_comment_is_not_a_document(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text("<p></p>\n  {#python\n  x = 1\n  #}\n")

    result = manifest.describe([Path(".")])

    assert [c["kind"] for c in result["components"] if not c["builtin"]] == ["template"]


def test_a_python_block_document_no_sys_path_entry_holds_has_no_module(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"src/ns/card.pjx": GOOD})

    result = manifest.describe([Path("src")], [Path("other")])

    card = next(c for c in result["components"] if not c["builtin"])
    assert card["class"]["module"] is None
    assert "no-module-name" in [d["code"] for d in result["diagnostics"]]


def test_a_package_init_module_is_named_for_its_package(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")

    assert sfc.module_name_for(tmp_path / "pkg" / "__init__.py") == "pkg"


def test_a_diagnostic_in_a_py_template_has_the_modules_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "chip.py").write_text(
        'class Chip:\n    template = """\n        <p></p>\n        {#css x #}\n'
        '        {#css\n        a {}\n        #}\n        {#css\n        b {}\n        #}\n    """\n'
    )

    found = _one(manifest.describe([Path("chip.py")])["diagnostics"], "second-block")

    assert _at(found)[1] == 8


def test_a_range_ends_where_it_starts_or_later(tree):
    (tree / "app/ui/early.pjx").write_text('{#python\nx = "#}"\n#}\n<p></p>\n')

    for diagnostic in manifest.describe([Path("app")])["diagnostics"]:
        start, end = diagnostic["range"]["start"], diagnostic["range"]["end"]
        assert (end["line"], end["column"]) >= (start["line"], start["column"])


def test_an_unhashable_literal_in_a_header_or_a_field_does_not_stop_the_run(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path,
        {
            "bad_header.pjx": "{#def f: int = {[1]: 2} #}\n<p></p>\n",
            "bad_field.py": "class BadField:\n    f: Literal[{[1]: 2}] = 1\n    template = '<p></p>'\n",
            "fine.pjx": "<p></p>\n",
        },
    )

    result = manifest.describe([Path(".")])

    mine = {c["tag"]: c for c in result["components"] if not c["builtin"]}
    assert set(mine) == {"BadHeader", "BadField", "Fine"}
    assert mine["BadField"]["props"][0]["literal_values"] is None
    assert [d["code"] for d in result["diagnostics"]] == ["def-header-invalid"]


def test_an_unexpected_failure_in_one_file_is_a_diagnostic_for_that_file(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"bad.pjx": "<p></p>\n", "fine.pjx": "<p></p>\n"})
    real = manifest._template_component

    def explode(project, document):
        if document.path.stem == "bad":
            raise RuntimeError("boom")
        return real(project, document)

    monkeypatch.setattr(manifest, "_template_component", explode)

    result = manifest.describe([Path(".")])

    assert [c["tag"] for c in result["components"] if not c["builtin"]] == ["Fine"]
    found = _one(result["diagnostics"], "internal-error")
    assert (found["path"], found["severity"]) == (_abs("bad.pjx"), "error")
    assert "boom" in found["message"]


def test_a_stdin_buffer_reports_each_collision_once(tree, monkeypatch, capsys):
    _stdin(
        monkeypatch,
        "class Chip:\n    template = '<i></i>'\n\n\nclass Chip:\n    template = '<b></b>'\n",
    )

    manifest.main(["--stdin", "--filename", "app/ui/other.py"])

    result = json.loads(capsys.readouterr().out)
    # Two classes in the buffer, each warned about once.
    assert [d["code"] for d in result["diagnostics"]] == ["tag-collision"] * 2


def test_a_collision_with_a_builtin_is_reported_on_the_user_file_only(tree):
    found = _collisions(tree, mine="class PjxBadge:\n    template = '<i></i>'\n")

    assert {d["path"] for d in found} == {_abs("app/ui/mine.py")}


def test_strict_is_null_when_no_class_was_found_and_false_only_for_templates(tree):
    (tree / "app/ui/nope.pjx").write_text(
        "{#python\nclass Other:\n    pass\n#}\n<p></p>\n"
    )

    found = _components(tree)

    assert found["Nope"]["strict"] is None
    assert found["Badge"]["strict"] is False


def test_a_zero_width_range_is_widened_to_the_end_of_its_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    unclosed = _one(
        _document(tmp_path, "{#def a, ( #}\n<p></p>\n"), "def-header-invalid"
    )
    syntax = _one(
        _document(tmp_path, "{#python\nx = (\n#}\n<p></p>\n", "card.pjx"),
        "python-syntax-error",
    )

    for found in (unclosed, syntax):
        assert found["range"]["end"] != found["range"]["start"], found


def test_a_template_is_named_by_its_stem(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x_2.pjx").write_text("<p></p>\n")

    result = manifest.describe([Path(".")])

    assert next(c for c in result["components"] if c["tag"] == "X2")["name"] == "x_2"


def test_a_raw_protected_example_is_a_template_not_a_document(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "guide.pjx").write_text(
        "{% raw %}\n{#python\nx = 1\n#}\n{% endraw %}\n<p></p>\n"
    )

    result = manifest.describe([Path(".")])

    mine = {c["tag"]: c for c in result["components"] if not c["builtin"]}
    assert mine["Guide"]["kind"] == "template"
    assert not [d for d in result["diagnostics"] if d["path"].endswith(".pjx")]
