"""Tests for manifest diagnostics, stdin mode and the command line."""

import json
import sys
from pathlib import Path

import pytest

from pyjinhx import manifest
from pyjinhx.document import scanner
from tests.unit.manifest._helpers import (
    CARD_PY,
    GOOD,
    _abs,
    _at,
    _document,
    _grammar,
    _one,
    _stdin,
)

CORPUS = Path(__file__).resolve().parents[2] / "fixtures" / "block_grammar"


def _diagnostics(root: Path, *where: str) -> list[dict]:
    return manifest.describe([Path(w) for w in where] or [Path(".")])["diagnostics"]


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

    assert scanner.module_name_for(tmp_path / "pkg/sub/card.pjx") == "pkg.sub.card"
    assert scanner.module_name_for(tmp_path / "pkg/sub/__init__.py") == "pkg.sub"
    assert scanner.module_name_for(tmp_path / "loose/card.pjx") == "card"
    assert scanner.module_name_for(tmp_path / "pkg/not_yet/card.pjx") == "card"


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
