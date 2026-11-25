"""The import hook that makes a ``.pjx`` document with a ``{#python`` block an
ordinary module: found on the search path, executed like a ``.py`` file."""

import importlib
import importlib.util
import inspect
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

import pytest

import pyjinhx  # noqa: F401  (installs the finder)

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
