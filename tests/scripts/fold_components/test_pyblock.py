"""Tests for fold_components pyblock: folding a component module into its pjx python block."""

import importlib
import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.scripts.fold_components._helpers import (
    CARD_CSS,
    CARD_PJX,
    CARD_PY,
    SCRIPT,
    make_card,
    refused,
    run,
    write,
)

# --- the command line ---------------------------------------------------------


# --- pyblock ----------------------------------------------------------------

_packages = iter(range(10_000))


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh importable package directory under ``tmp_path``."""
    directory = tmp_path / f"fold_pkg_{next(_packages)}"
    write(directory / "__init__.py", "")
    monkeypatch.syspath_prepend(str(tmp_path))
    return directory


def import_fresh(module: str, monkeypatch: pytest.MonkeyPatch):
    """``module`` imported by name, forgotten again when the test ends."""
    importlib.invalidate_caches()
    for name in [n for n in sys.modules if n == module or n.startswith(f"{module}.")]:
        monkeypatch.delitem(sys.modules, name)
    imported = importlib.import_module(module)
    monkeypatch.delitem(sys.modules, module)
    return imported


def test_pyblock_folds_the_module_into_its_pjx_and_renders_the_same(
    package, monkeypatch, capsys
):
    write(package / "card.py", CARD_PY)
    write(package / "card.pjx", CARD_PJX)
    write(package / "card.css", CARD_CSS)
    module = f"{package.name}.card"
    before = import_fresh(module, monkeypatch).Card(id="c", title="hi").render()

    code, out = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert not (package / "card.py").exists()
    assert (package / "card.css").exists()
    folded = (package / "card.pjx").read_text()
    assert (
        folded
        == "{#python\n" + textwrap.dedent(CARD_PY).lstrip("\n") + "#}\n" + CARD_PJX
    )
    assert import_fresh(module, monkeypatch).Card(id="c", title="hi").render() == before
    assert "1 folded" in out


def test_pyblock_folds_a_module_with_imports_helpers_and_a_relative_import(
    package, monkeypatch, capsys
):
    write(package / "util.py", "SUFFIX = '!'\n")
    write(
        package / "card.py",
        '''
        """A card."""
        from __future__ import annotations

        from pyjinhx import BaseComponent

        from .util import SUFFIX


        def shout(text: str) -> str:
            return text + SUFFIX


        class Card(BaseComponent):
            title: str

            def model_post_init(self, context) -> None:
                self.title = shout(self.title)
        ''',
    )
    write(package / "card.pjx", "<b>{{ title }}</b>\n")
    module = f"{package.name}.card"
    before = import_fresh(module, monkeypatch).Card(id="c", title="hi").render()

    code, _ = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert import_fresh(module, monkeypatch).Card(id="c", title="hi").render() == before


def test_pyblock_reports_a_second_class_that_keeps_its_own_pjx(
    package, monkeypatch, capsys
):
    write(
        package / "card.py",
        CARD_PY + "\n\n    class Chip(BaseComponent):\n        label: str = ''\n",
    )
    write(package / "card.pjx", CARD_PJX)
    write(package / "chip.pjx", "<i>{{ label }}</i>\n")

    code, out = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert "Chip keeps its chip.pjx" in out
    assert (package / "chip.pjx").exists()
    chip = import_fresh(f"{package.name}.card", monkeypatch).Chip
    assert chip(id="x", label="a").render() == "<i>a</i>"


def test_pyblock_refuses_source_with_a_block_closer_and_names_the_line(
    tmp_path, capsys
):
    make_card(tmp_path)
    (tmp_path / "card.py").write_text(
        textwrap.dedent(CARD_PY).lstrip("\n") + "\nEND = '#}'\n"
    )
    refused(tmp_path, "`#}` on line 7", capsys)


def test_pyblock_refuses_a_module_with_no_class_named_for_it(tmp_path, capsys):
    write(tmp_path / "other.py", CARD_PY)
    write(tmp_path / "other.pjx", CARD_PJX)
    refused(tmp_path, "no class named for other", capsys, tmp_path / "other.py")


def test_pyblock_refuses_a_package_init(tmp_path, capsys):
    write(tmp_path / "__init__.py", CARD_PY)
    refused(tmp_path, "__init__.py", capsys, tmp_path / "__init__.py")


def test_pyblock_refuses_a_class_without_a_pjx_of_its_own(tmp_path, capsys):
    write(tmp_path / "card.py", CARD_PY)
    refused(
        tmp_path,
        "there is no card.pjx beside it",
        capsys,
        tmp_path / "card.py",
    )


def test_pyblock_walk_skips_a_component_class_with_no_pjx_beside_it(tmp_path, capsys):
    write(tmp_path / "user.py", CARD_PY.replace("Card", "User"))

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 0 and "0 folded, 0 refused" in out


def test_pyblock_refuses_a_class_that_assigns_its_template(tmp_path, capsys):
    make_card(tmp_path)
    write(
        tmp_path / "card.py",
        CARD_PY + "        template = '<i></i>'\n",
    )
    refused(tmp_path, "assigns its own `template`", capsys)


def test_pyblock_refuses_a_pjx_that_already_holds_a_python_block(tmp_path, capsys):
    make_card(tmp_path, "{#python\nx = 1\n#}\n" + CARD_PJX)
    refused(tmp_path, "already has a {#python block", capsys)


def test_pyblock_refuses_a_pjx_with_a_def_header(tmp_path, capsys):
    make_card(tmp_path, "{#def title: str #}\n" + CARD_PJX)
    refused(tmp_path, "already has a {#def#} header", capsys)


def test_pyblock_refuses_a_pjx_with_no_markup(tmp_path, capsys):
    make_card(tmp_path, "{# only a comment #}\n")
    refused(tmp_path, "has no markup", capsys)


def test_pyblock_refuses_when_a_directory_would_shadow_the_module(tmp_path, capsys):
    make_card(tmp_path)
    (tmp_path / "card").mkdir()
    refused(tmp_path, "a card/ directory", capsys)


def test_pyblock_reports_every_line_under_the_root_that_names_the_file(
    tmp_path, capsys
):
    components = tmp_path / "components"
    make_card(components)
    write(tmp_path / "setup.py", "FILES = ['components/card.py']\n")
    write(tmp_path / "other.py", "print('nothing')\n")

    code, out = run("pyblock", components, "--root", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert "setup.py:1:" in out and "other.py" not in out
    assert "1 references" in out


def test_pyblock_dry_run_writes_nothing_and_a_second_write_is_a_no_op(tmp_path, capsys):
    make_card(tmp_path)

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 0
    assert "+{#python" in out and "-class Card" in out
    assert (tmp_path / "card.py").exists()
    assert (tmp_path / "card.pjx").read_text() == CARD_PJX

    run("pyblock", tmp_path, "--write", capsys=capsys)
    folded = (tmp_path / "card.pjx").read_text()
    code, out = run("pyblock", tmp_path, "--write", capsys=capsys)

    assert code == 0 and "0 folded, 0 refused" in out
    assert (tmp_path / "card.pjx").read_text() == folded


def test_pyblock_reminds_about_the_stubs_and_what_must_import_pyjinhx(tmp_path, capsys):
    make_card(tmp_path)

    _, out = run("pyblock", tmp_path, capsys=capsys)

    assert "something must import pyjinhx before this module" in out
    assert "python -m pyjinhx.stubgen" in out


def test_pyblock_asks_for_the_import_only_when_the_package_root_lacks_it(
    package, capsys
):
    write(package / "card.py", CARD_PY)
    write(package / "card.pjx", CARD_PJX)

    _, out = run("pyblock", package, capsys=capsys)
    assert f"{package / '__init__.py'} needs `import pyjinhx`" in out

    (package / "__init__.py").write_text("import pyjinhx\n")
    _, out = run("pyblock", package, capsys=capsys)
    assert "needs `import pyjinhx`" not in out and "something must import" not in out


def test_pyblock_drops_a_byte_order_mark_from_either_file(package, capsys):
    (package / "card.py").write_bytes(
        b"\xef\xbb\xbf" + textwrap.dedent(CARD_PY).lstrip("\n").encode()
    )
    (package / "card.pjx").write_bytes(b"\xef\xbb\xbf" + CARD_PJX.encode())

    code, _ = run("pyblock", package, "--write", capsys=capsys)

    assert code == 0
    assert "\ufeff" not in (package / "card.pjx").read_text(encoding="utf-8")


def test_pyblock_refuses_a_header_behind_a_byte_order_mark(tmp_path, capsys):
    make_card(tmp_path)
    (tmp_path / "card.pjx").write_bytes(b"\xef\xbb\xbf{#def title: str #}\n")
    refused(tmp_path, "already has a {#def#} header", capsys)


def test_pyblock_refuses_a_named_file_that_is_not_python_but_skips_it_in_a_walk(
    tmp_path, capsys
):
    broken = write(tmp_path / "card.py", "class Card(:\n")
    write(tmp_path / "card.pjx", CARD_PJX)

    code, out = run("pyblock", tmp_path, capsys=capsys)
    assert code == 0 and "0 refused" in out

    refused(tmp_path, "not valid Python", capsys, broken)


def test_pyblock_reports_references_in_hidden_files_but_not_hidden_directories(
    tmp_path, capsys
):
    components = tmp_path / "components"
    make_card(components)
    write(tmp_path / ".coveragerc", "omit = components/card.py\n")
    write(tmp_path / ".github" / "ci.yml", "run: python components/card.py\n")

    _, out = run("pyblock", components, "--root", tmp_path, capsys=capsys)

    assert ".coveragerc:1:" in out
    assert "ci.yml" not in out


def test_pyblock_notes_a_module_that_reads_its_own_file_or_main(tmp_path, capsys):
    write(
        tmp_path / "card.py",
        CARD_PY + "\n    HERE = __file__\n",
    )
    write(tmp_path / "card.pjx", CARD_PJX)

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 0
    assert "__file__ becomes card.pjx" in out and "python card.py" in out


def test_pyblock_says_when_the_pjx_already_holds_this_module(tmp_path, capsys):
    make_card(tmp_path)
    folded = "{#python\n" + textwrap.dedent(CARD_PY).lstrip("\n") + "#}\n" + CARD_PJX
    (tmp_path / "card.pjx").write_text(folded)

    code, out = run("pyblock", tmp_path, capsys=capsys)

    assert code == 1
    assert "already folded; delete card.py" in out


def test_pyblock_writes_through_a_temporary_file_and_leaves_none_behind(
    tmp_path, capsys
):
    make_card(tmp_path)

    run("pyblock", tmp_path, "--write", capsys=capsys)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["card.pjx"]


def test_the_script_runs_as_a_command_and_exits_non_zero_on_a_refusal(tmp_path):
    make_card(tmp_path)
    write(tmp_path / "card.css", "a { content: '#}'; }\n")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "assets", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "refused" in result.stdout
    assert (tmp_path / "card.css").exists()


def test_only_the_given_paths_are_touched(tmp_path, capsys):
    for name in ("mine", "theirs"):
        write(tmp_path / name / "card.py", CARD_PY)
        write(tmp_path / name / "card.pjx", CARD_PJX)
        write(tmp_path / name / "card.css", CARD_CSS)

    run("assets", tmp_path / "mine", "--write", capsys=capsys)
    run("template", tmp_path / "mine", "--write", capsys=capsys)

    assert (tmp_path / "theirs" / "card.css").exists()
    assert (tmp_path / "theirs" / "card.pjx").read_text() == CARD_PJX
    assert not (tmp_path / "mine" / "card.pjx").exists()
