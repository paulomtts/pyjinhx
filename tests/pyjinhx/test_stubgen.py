"""The stub generator: a `.pjx` block's Python as a line-preserving `.pyi`."""

import ast

import pytest

from pyjinhx import sfc, stubgen

CARD = """\
{#python
from pyjinhx import ReactiveComponent

from app.todos import Keys, store


class TodoCount(ReactiveComponent, react={Keys.TODOS}):
    remaining: int = 0

    @classmethod
    def load(cls) -> "TodoCount":
        return cls(remaining=store.remaining())
#}
<div class="counter">{{ remaining }} left</div>
"""


def _stub(source: str) -> str:
    stub = stubgen.generate_stub(source, "card.pjx")
    assert stub is not None
    return stub


def _declarations(source: str) -> list[tuple[str, str, int]]:
    """Every class, def and annotated name outside a function body, with its line."""
    found = []

    def visit(node: ast.AST) -> None:
        match node:
            case ast.ClassDef() | ast.FunctionDef() | ast.AsyncFunctionDef():
                found.append((type(node).__name__, node.name, node.lineno))
            case ast.AnnAssign(target=ast.Name(id=name)):
                found.append(("AnnAssign", name, node.lineno))
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.iter_child_nodes(node):
                visit(child)

    visit(ast.parse(source))
    return sorted(found)


def _document(python: str) -> str:
    return "{#python\n" + python + "#}\n<p></p>\n"


def test_a_document_without_a_block_has_no_stub():
    assert stubgen.generate_stub("<p></p>\n", "card.pjx") is None


def test_declarations_keep_their_line_numbers():
    padded = sfc.python_source(CARD, "card.pjx")
    assert padded is not None
    assert _declarations(_stub(CARD)) == _declarations(padded)


def test_function_bodies_become_an_ellipsis():
    stub = ast.parse(_stub(CARD))
    load = stub.body[-1].body[-1]  # type: ignore[attr-defined]
    assert isinstance(load, ast.FunctionDef)
    assert ast.dump(load.body[0]) == ast.dump(ast.Expr(ast.Constant(...)))


def test_everything_but_function_bodies_is_untouched():
    stub = _stub(CARD)
    assert "class TodoCount(ReactiveComponent, react={Keys.TODOS}):" in stub
    assert "    remaining: int = 0" in stub
    assert "    @classmethod" in stub
    assert '    def load(cls) -> "TodoCount":' in stub
    assert "from app.todos import Keys, store" in stub


def test_the_opener_line_holds_the_marker():
    lines = _stub(CARD).split("\n")
    assert lines[0] == "# pyjinhx.stubgen: generated from card.pjx; do not edit"


def test_the_marker_sits_on_the_openers_line_when_markup_comes_first():
    stub = _stub("<p></p>\n\n" + CARD)
    assert stub.split("\n")[2] == stubgen.marker("card.pjx")


def test_the_stub_ends_on_the_closers_line():
    source = CARD + "<p>{{ 1 }}</p>\n" * 5
    block = sfc.python_block(source, "card.pjx")
    assert block is not None
    assert _stub(source).count("\n") + 1 == block.close_line


@pytest.mark.parametrize(
    "python",
    [
        "def f():\n    x = 1\n    y = (\n        2\n    )\n    return x + y\n",
        "def f(): return 1\n",
        'def f():\n    """Only a docstring."""\n',
        "async def f():\n    await g()\n",
        "def f():\n    def inner():\n        return 1\n    return inner\n",
        "def f(): a = 1; return a\n",
        "def f():\n    return 'é'  # çà\n",
        "def f(): return 'é' + 'ü'\n",
        (
            "class C:\n    @property\n    def p(self) -> int:\n        return 1\n\n"
            "    @classmethod\n    def c(cls): pass\n"
        ),
        "if True:\n    def f():\n        return 1\n",
    ],
)
def test_every_way_of_writing_a_body_keeps_the_lines_after_it(python):
    source = _document(python + "\nclass After:\n    n: int = 1\n")
    stub = _stub(source)
    padded = sfc.python_source(source, "card.pjx")
    assert padded is not None
    assert _declarations(stub) == _declarations(padded)
    assert "return" not in stub and "await" not in stub


def test_a_decorator_and_its_arguments_survive():
    source = _document(
        "class C:\n    @field_validator('a', mode='before')\n"
        "    def v(cls, x):\n        return x\n"
    )
    assert "@field_validator('a', mode='before')" in _stub(source)


def test_a_block_that_is_not_python_is_a_syntax_error_on_its_line():
    with pytest.raises(SyntaxError) as raised:
        stubgen.generate_stub(_document("x = 1\ndef (:\n"), "card.pjx")
    assert raised.value.lineno == 3


def test_generating_runs_nothing(tmp_path):
    sentinel = tmp_path / "ran"
    source = _document(f"open({str(sentinel)!r}, 'w').close()\n")
    stubgen.generate_stub(source, "card.pjx")
    assert not sentinel.exists()


def _tree(tmp_path, files: dict[str, str]):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_main_writes_a_stub_beside_each_block_and_none_without(tmp_path):
    _tree(tmp_path, {"ui/card.pjx": CARD, "ui/plain.pjx": "<p></p>\n"})
    assert stubgen.main([str(tmp_path)]) == 0
    assert (tmp_path / "ui/card.pyi").read_text() == _stub(CARD)
    assert not (tmp_path / "ui/plain.pyi").exists()


def test_a_second_run_rewrites_nothing(tmp_path):
    _tree(tmp_path, {"card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    before = (tmp_path / "card.pyi").stat().st_mtime_ns
    assert stubgen.main([str(tmp_path)]) == 0
    assert (tmp_path / "card.pyi").stat().st_mtime_ns == before


def test_a_changed_block_regenerates_its_stub(tmp_path):
    _tree(tmp_path, {"card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    (tmp_path / "card.pjx").write_text(CARD.replace("remaining", "left"))
    stubgen.main([str(tmp_path)])
    assert "left: int = 0" in (tmp_path / "card.pyi").read_text()


def test_a_hand_written_stub_is_not_overwritten(tmp_path, capsys):
    _tree(tmp_path, {"card.pjx": CARD, "card.pyi": "class Mine: ...\n"})
    assert stubgen.main([str(tmp_path)]) == 2
    assert (tmp_path / "card.pyi").read_text() == "class Mine: ...\n"
    assert "card.pyi" in capsys.readouterr().err


def test_a_stub_whose_document_was_deleted_is_removed(tmp_path):
    _tree(tmp_path, {"card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    (tmp_path / "card.pjx").unlink()
    assert stubgen.main([str(tmp_path)]) == 0
    assert not (tmp_path / "card.pyi").exists()


def test_a_stub_whose_document_lost_its_block_is_removed(tmp_path):
    _tree(tmp_path, {"card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    (tmp_path / "card.pjx").write_text("<p></p>\n")
    stubgen.main([str(tmp_path)])
    assert not (tmp_path / "card.pyi").exists()


def test_an_unmarked_stub_without_a_document_is_left_alone(tmp_path):
    _tree(tmp_path, {"other.pyi": "x: int\n"})
    assert stubgen.main([str(tmp_path)]) == 0
    assert (tmp_path / "other.pyi").exists()


def test_check_is_quiet_and_writes_nothing_when_stubs_are_fresh(tmp_path, capsys):
    _tree(tmp_path, {"card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    capsys.readouterr()
    assert stubgen.main([str(tmp_path), "--check"]) == 0
    assert capsys.readouterr().err == ""


def test_check_reports_a_missing_stub_and_writes_nothing(tmp_path, capsys):
    _tree(tmp_path, {"card.pjx": CARD})
    assert stubgen.main([str(tmp_path), "--check"]) == 1
    assert "card.pyi: missing" in capsys.readouterr().err
    assert not (tmp_path / "card.pyi").exists()


def test_check_reports_a_stale_stub(tmp_path, capsys):
    _tree(tmp_path, {"card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    (tmp_path / "card.pjx").write_text(CARD.replace("remaining", "left"))
    stale = (tmp_path / "card.pyi").read_text()
    assert stubgen.main([str(tmp_path), "--check"]) == 1
    assert "card.pyi: stale" in capsys.readouterr().err
    assert (tmp_path / "card.pyi").read_text() == stale


def test_check_reports_an_orphaned_stub_and_keeps_it(tmp_path, capsys):
    _tree(tmp_path, {"card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    (tmp_path / "card.pjx").unlink()
    assert stubgen.main([str(tmp_path), "--check"]) == 1
    assert "card.pyi: orphaned" in capsys.readouterr().err
    assert (tmp_path / "card.pyi").exists()


@pytest.mark.parametrize("shadow", ["card.py", "card/__init__.py"])
def test_check_reports_a_module_that_shadows_a_block(tmp_path, capsys, shadow):
    _tree(tmp_path, {"card.pjx": CARD, shadow: ""})
    stubgen.main([str(tmp_path)])
    assert stubgen.main([str(tmp_path), "--check"]) == 1
    assert "card.pjx: shadowed" in capsys.readouterr().err


def test_check_reports_each_problem_on_its_own_line(tmp_path, capsys):
    _tree(tmp_path, {"a.pjx": CARD, "b.pjx": CARD})
    assert stubgen.main([str(tmp_path), "--check"]) == 1
    assert len(capsys.readouterr().err.strip().splitlines()) == 2


def test_a_block_that_does_not_parse_is_reported_and_the_rest_still_runs(
    tmp_path, capsys
):
    _tree(tmp_path, {"a.pjx": _document("x = 1\ndef (:\n"), "b.pjx": CARD})
    assert stubgen.main([str(tmp_path)]) == 1
    assert "a.pjx:3" in capsys.readouterr().err
    assert (tmp_path / "b.pyi").exists()
    assert not (tmp_path / "a.pyi").exists()


def test_a_malformed_block_is_reported_with_its_line(tmp_path, capsys):
    _tree(tmp_path, {"a.pjx": "<p></p>\n  {#python\nx = 1\n#}\n"})
    assert stubgen.main([str(tmp_path)]) == 1
    assert "a.pjx:2" in capsys.readouterr().err


def test_main_never_runs_a_block(tmp_path):
    sentinel = tmp_path / "ran"
    _tree(tmp_path, {"card.pjx": _document(f"open({str(sentinel)!r}, 'w').close()\n")})
    stubgen.main([str(tmp_path)])
    assert not sentinel.exists()


def test_a_single_file_path_is_accepted(tmp_path):
    _tree(tmp_path, {"card.pjx": CARD, "other.pjx": CARD})
    assert stubgen.main([str(tmp_path / "card.pjx")]) == 0
    assert (tmp_path / "card.pyi").exists()
    assert not (tmp_path / "other.pyi").exists()


def test_hidden_and_vendored_directories_are_skipped(tmp_path):
    _tree(tmp_path, {".venv/card.pjx": CARD, "node_modules/card.pjx": CARD})
    stubgen.main([str(tmp_path)])
    assert not list(tmp_path.rglob("*.pyi"))


def test_a_utf8_bom_does_not_hide_the_block(tmp_path):
    (tmp_path / "card.pjx").write_bytes(b"\xef\xbb\xbf" + CARD.encode())
    stubgen.main([str(tmp_path)])
    assert (tmp_path / "card.pyi").read_text() == _stub(CARD)


def test_sync_is_the_api_for_tools_that_do_not_want_a_cli(tmp_path):
    _tree(tmp_path, {"card.pjx": CARD})
    found = stubgen.sync([tmp_path], write=False)
    assert [(f.path.name, f.kind) for f in found] == [("card.pyi", "missing")]
    assert stubgen.sync([tmp_path], write=True) == found
    assert stubgen.sync([tmp_path], write=False) == []


def test_python_m_stubgen_help_runs():
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "pyjinhx.stubgen", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0
    assert "--check" in done.stdout


def test_a_document_that_is_not_utf8_is_reported_and_the_rest_still_runs(
    tmp_path, capsys
):
    _tree(tmp_path, {"b.pjx": CARD, "gone.pyi": stubgen.marker("gone.pjx") + "\n"})
    (tmp_path / "a.pjx").write_bytes(b"<p>\xff</p>\n")
    assert stubgen.main([str(tmp_path)]) == 1
    assert "a.pjx: invalid" in capsys.readouterr().err
    assert (tmp_path / "b.pyi").exists()
    assert not (tmp_path / "gone.pyi").exists()


@pytest.mark.parametrize(
    "folder",
    [
        "env/lib/python3.13/site-packages/pkg",
        "env/dist-packages/pkg",
        "build/lib",
        "dist",
        "myenv",
    ],
)
def test_virtualenvs_and_build_output_are_skipped(tmp_path, folder):
    _tree(tmp_path, {f"{folder}/card.pjx": CARD, "myenv/pyvenv.cfg": ""})
    stubgen.main([str(tmp_path)])
    assert not list(tmp_path.rglob("*.pyi"))


@pytest.mark.parametrize("shadow", ["card.py", "card/__init__.py"])
def test_a_shadowed_block_gets_no_stub_to_win_over_the_module(tmp_path, shadow):
    _tree(tmp_path, {"card.pjx": CARD, shadow: ""})
    assert stubgen.main([str(tmp_path)]) == 1
    assert not (tmp_path / "card.pyi").exists()


def test_a_stub_already_there_for_a_shadowed_block_is_left_alone(tmp_path):
    old = stubgen.marker("card.pjx") + "\n"
    _tree(tmp_path, {"card.pjx": CARD, "card.py": "", "card.pyi": old})
    stubgen.main([str(tmp_path)])
    assert (tmp_path / "card.pyi").read_text() == old


def test_an_init_body_is_kept_so_its_attributes_stay_declared():
    source = _document(
        "class C:\n    def __init__(self):\n        self.x = 1\n"
        "        self.y: int = 2\n\n    def run(self):\n        return self.x\n"
    )
    stub = _stub(source)
    assert "        self.x = 1" in stub
    assert "        self.y: int = 2" in stub
    assert "return" not in stub
    assert _declarations(stub) == _declarations(
        sfc.python_source(source, "card.pjx") or ""
    )


def test_a_path_that_does_not_exist_is_reported_and_exits_2(tmp_path, capsys):
    assert stubgen.main([str(tmp_path / "nope")]) == 2
    assert "nope: no such file or directory" in capsys.readouterr().err


def test_a_finding_carries_the_blocks_error_code_and_column(tmp_path):
    _tree(tmp_path, {"a.pjx": "<p></p>\n  {#python\nx = 1\n#}\n"})
    (finding,) = stubgen.sync([tmp_path], write=False)
    assert finding.line == 2
    assert finding.code
    assert finding.column


def test_a_python_syntax_error_finding_has_its_column(tmp_path):
    _tree(tmp_path, {"a.pjx": _document("x = 1\ndef (:\n")})
    (finding,) = stubgen.sync([tmp_path], write=False)
    assert (finding.line, finding.column) == (3, 5)


def test_a_stub_that_cannot_be_written_is_a_finding_not_a_crash(tmp_path, capsys):
    _tree(tmp_path, {"ui/a.pjx": CARD, "b.pjx": CARD})
    (tmp_path / "ui").chmod(0o500)
    try:
        assert stubgen.main([str(tmp_path)]) == 1
    finally:
        (tmp_path / "ui").chmod(0o700)
    err = capsys.readouterr().err
    assert "a.pyi: failed" in err and "wrote" not in err and "removed" not in err
    assert (tmp_path / "b.pyi").exists()


def test_an_orphan_that_cannot_be_removed_is_a_finding_not_a_crash(tmp_path, capsys):
    _tree(tmp_path, {"ui/a.pyi": stubgen.marker("a.pjx") + "\n"})
    (tmp_path / "ui").chmod(0o500)
    try:
        assert stubgen.main([str(tmp_path)]) == 1
    finally:
        (tmp_path / "ui").chmod(0o700)
    err = capsys.readouterr().err
    assert "a.pyi: failed" in err and "wrote" not in err and "removed" not in err


def test_the_block_is_parsed_once(monkeypatch):
    calls = []
    real = stubgen.python_block
    monkeypatch.setattr(stubgen, "python_block", lambda *a: calls.append(a) or real(*a))
    _stub(CARD)
    assert len(calls) == 1


def test_crlf_input_gives_a_stub_with_only_lf(tmp_path):
    crlf = CARD.replace("\n", "\r\n")
    assert "\r" not in _stub(crlf)
    assert _stub(crlf) == _stub(CARD)
    (tmp_path / "card.pjx").write_bytes(crlf.encode())
    stubgen.main([str(tmp_path)])
    assert b"\r" not in (tmp_path / "card.pyi").read_bytes()


def test_walk_finds_files_by_suffix_and_skips_what_sync_skips(tmp_path):
    for name in ("a/card.pjx", "a/card.py", "a/card.pyi", ".hidden/x.py"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "pyvenv.cfg").write_text("")
    (tmp_path / "venv" / "lib.py").write_text("")

    found = stubgen.walk([tmp_path], {".pjx", ".py"})

    assert found == {
        ".pjx": [tmp_path / "a" / "card.pjx"],
        ".py": [tmp_path / "a" / "card.py"],
    }
