"""The import hook that makes a ``.pjx`` document with a ``{#python`` block an
ordinary module: found on the search path, executed like a ``.py`` file."""

import importlib
import importlib.util
import inspect
import os
import subprocess
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

import pytest

import pyjinhx
from pyjinhx import importer

Write = Callable[[str, str], Path]

CARD = """\
{#python
from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str = ""
#}
<div>{{ title }}</div>
"""


@pytest.fixture
def write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Write files under ``tmp_path``, which is on ``sys.path``; modules the
    test imported from there are forgotten afterwards."""
    monkeypatch.syspath_prepend(str(tmp_path))
    before = set(sys.modules)

    def write_file(name: str, text: str) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        importlib.invalidate_caches()
        return path

    write_file("pkg/__init__.py", "")
    yield write_file
    for name in set(sys.modules) - before:
        del sys.modules[name]


def test_a_block_document_imports_as_a_module(write: Write):
    path = write("pkg/card.pjx", CARD)
    card = importlib.import_module("pkg.card")
    assert card.Card.__module__ == "pkg.card"
    assert card.__file__ == str(path)
    assert card.__spec__.origin == str(path)
    assert card.__package__ == "pkg"


def test_from_import_and_package_reexport(write: Write):
    write("pkg/__init__.py", "from .card import Card\n")
    write("pkg/card.pjx", CARD)
    from pkg import Card  # type: ignore[import-not-found]

    assert Card.__module__ == "pkg.card"


def test_a_relative_import_inside_the_block(write: Write):
    write("pkg/helpers.py", "def shout(text):\n    return text.upper()\n")
    write(
        "pkg/card.pjx",
        "{#python\nfrom .helpers import shout\nLOUD = shout('hi')\n#}\n<p></p>\n",
    )
    assert importlib.import_module("pkg.card").LOUD == "HI"


def test_one_document_imports_a_class_from_another(write: Write):
    write("pkg/card.pjx", CARD)
    write(
        "pkg/panel.pjx",
        "{#python\nfrom pkg.card import Card\nSAME = Card\n#}\n<p></p>\n",
    )
    assert (
        importlib.import_module("pkg.panel").SAME
        is importlib.import_module("pkg.card").Card
    )


def test_a_document_without_a_block_is_not_a_module(write: Write):
    write("pkg/plain.pjx", "<div>{#def title: str #}</div>\n")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pkg.plain")


def test_a_sibling_py_module_wins(write: Write):
    write("pkg/card.py", "WHICH = 'py'\n")
    write("pkg/card.pjx", CARD)
    assert importlib.import_module("pkg.card").WHICH == "py"


def test_find_spec_answers_for_a_block_document(write: Write):
    path = write("pkg/card.pjx", CARD)
    spec = importlib.util.find_spec("pkg.card")
    assert spec is not None
    assert spec.origin == str(path)
    assert spec.cached is None
    assert spec.submodule_search_locations is None


def test_a_syntax_error_names_the_pjx_line(write: Write):
    path = write("pkg/card.pjx", "<p></p>\n{#python\nx = 1\ny = = 2\n#}\n")
    with pytest.raises(SyntaxError) as raised:
        importlib.import_module("pkg.card")
    assert raised.value.filename == str(path)
    assert raised.value.lineno == 4


def test_a_traceback_shows_the_pjx_path_line_and_text(write: Write):
    path = write(
        "pkg/card.pjx",
        "<p></p>\n{#python\ndef boom():\n    raise RuntimeError('no')\n#}\n",
    )
    card = importlib.import_module("pkg.card")
    with pytest.raises(RuntimeError) as raised:
        card.boom()
    last = traceback.extract_tb(raised.value.__traceback__)[-1]
    assert (last.filename, last.lineno) == (str(path), 4)
    assert "raise RuntimeError('no')" in "".join(
        traceback.format_exception(raised.value)
    )


def test_inspect_gets_the_source_of_a_function(write: Write):
    write("pkg/card.pjx", "<p></p>\n{#python\ndef shout():\n    return 'hi'\n#}\n")
    card = importlib.import_module("pkg.card")
    assert inspect.getsource(card.shout) == "def shout():\n    return 'hi'\n"


def test_the_loader_serves_the_padded_python(write: Write):
    from pyjinhx import sfc

    text = "<p></p>\n{#python\nVALUE = 1\n#}\n"
    path = write("pkg/card.pjx", text)
    card = importlib.import_module("pkg.card")
    assert card.__loader__.get_source("pkg.card") == sfc.python_source(text, str(path))
    assert card.__loader__.is_package("pkg.card") is False


def test_no_bytecode_is_written(write: Write):
    path = write("pkg/card.pjx", CARD)
    importlib.import_module("pkg.card")
    assert not list(path.parent.glob("__pycache__/card*"))


def finders() -> list[importer.PjxFinder]:
    return [f for f in sys.meta_path if isinstance(f, importer.PjxFinder)]


@pytest.fixture
def hook_state():
    """Leave the finder installed whatever a test did to it."""
    yield
    importer.uninstall()
    importer.install()


def test_install_appends_one_finder_at_the_end(hook_state):
    importer.uninstall()
    importer.install()
    importer.install()
    assert len(finders()) == 1
    assert sys.meta_path[-1] is finders()[0]


def test_uninstall_removes_the_finder(hook_state):
    importer.uninstall()
    assert finders() == []


def test_reloading_pyjinhx_keeps_one_finder(hook_state):
    importlib.reload(pyjinhx)
    assert len(finders()) == 1


def test_an_ordinary_import_never_asks_the_finder(
    write: Write, monkeypatch: pytest.MonkeyPatch
):
    asked: list[str] = []
    real = importer.PjxFinder.find_spec
    monkeypatch.setattr(
        importer.PjxFinder,
        "find_spec",
        lambda self, name, *args: asked.append(name) or real(self, name, *args),
    )
    write("plain_mod.py", "VALUE = 1\n")
    importlib.import_module("plain_mod")
    assert asked == []


def run(code: str, *args: str, cwd: Path | None = None, path: Path | None = None):
    env = {**os.environ, "PYTHONPATH": str(path)} if path else os.environ
    return subprocess.run(
        [sys.executable, *args, "-c", code] if code else [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


def test_import_pyjinhx_installs_the_finder_and_stays_light():
    result = run(
        "import sys, pyjinhx\n"
        "assert type(sys.meta_path[-1]).__name__ == 'PjxFinder', sys.meta_path\n"
        "assert 'pydantic' not in sys.modules and 'jinja2' not in sys.modules\n"
    )
    assert result.returncode == 0, result.stderr


def test_python_dash_m_runs_a_block_document(write: Write, tmp_path: Path):
    write("pkg/__init__.py", "import pyjinhx\n")
    write(
        "pkg/card.pjx",
        "{#python\nif __name__ == '__main__':\n    print('ran', __file__)\n#}\n<p></p>\n",
    )
    result = run("", "-m", "pkg.card", path=tmp_path, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"ran {tmp_path / 'pkg' / 'card.pjx'}"


def test_reload_runs_the_block_again(write: Write, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_RUNS", "0")
    write(
        "pkg/card.pjx",
        "{#python\nimport os\nos.environ['PJX_RUNS'] += 'x'\n#}\n<p></p>\n",
    )
    card = importlib.import_module("pkg.card")
    assert importlib.reload(card) is card
    assert os.environ["PJX_RUNS"] == "0xx"


def test_the_v0_opener_is_refused_with_the_fix(write: Write):
    path = write("pkg/card.pjx", "{# python\nX = 1\n#}\n<p></p>\n")
    with pytest.raises(ImportError, match="remove the space") as raised:
        importlib.import_module("pkg.card")
    assert str(path) in str(raised.value)
