"""The import hook that makes a ``.pjx`` document with a ``{#python`` block an
ordinary module: found on the search path, executed like a ``.py`` file."""

import importlib
import importlib.util
import inspect
import os
import subprocess
import sys
import traceback
from pathlib import Path

import pytest

import pyjinhx
from pyjinhx import importer, sfc
from tests.pyjinhx.conftest import Write

# The class a block needs for the file to be a document at all.
CLASS = """
from pyjinhx import BaseComponent


class Card(BaseComponent):
    pass
"""

CARD = """\
{#python
from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str = ""
#}
<div>{{ title }}</div>
"""


def test_a_block_document_imports_as_a_module(write: Write):
    path = write("pkg/card.pjx", CARD)
    card = importlib.import_module("pkg.card")
    assert card.Card.__module__ == "pkg.card"
    assert card.__file__ == str(path)
    assert card.__spec__ is not None
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
        "{#python\nfrom .helpers import shout\nLOUD = shout('hi')\n"
        + CLASS
        + "#}\n<p></p>\n",
    )
    assert importlib.import_module("pkg.card").LOUD == "HI"


def test_one_document_imports_a_class_from_another(write: Write):
    write("pkg/card.pjx", CARD)
    write(
        "pkg/panel.pjx",
        "{#python\nfrom pkg.card import Card\nSAME = Card\n"
        + CLASS.replace("Card", "Panel")
        + "#}\n<p></p>\n",
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
        "<p></p>\n{#python\ndef boom():\n    raise RuntimeError('no')\n"
        + CLASS
        + "#}\n",
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
    write(
        "pkg/card.pjx",
        "<p></p>\n{#python\ndef shout():\n    return 'hi'\n" + CLASS + "#}\n<p></p>\n",
    )
    card = importlib.import_module("pkg.card")
    assert inspect.getsource(card.shout) == "def shout():\n    return 'hi'\n"


def test_the_loader_serves_the_padded_python(write: Write):
    from pyjinhx import sfc

    text = "<p></p>\n{#python\nVALUE = 1\n" + CLASS + "#}\n"
    path = write("pkg/card.pjx", text)
    spec = importlib.import_module("pkg.card").__spec__
    loader = spec.loader if spec else None
    assert isinstance(loader, importer.PjxLoader)
    assert loader.get_source("pkg.card") == sfc.python_source(text, str(path))
    assert loader.is_package("pkg.card") is False


def test_no_bytecode_is_written(write: Write):
    path = write("pkg/card.pjx", CARD)
    importlib.import_module("pkg.card")
    assert not list(path.parent.glob("__pycache__/card*"))


def finders() -> list[importer.PjxFinder]:
    return [f for f in sys.meta_path if isinstance(f, importer.PjxFinder)]


def remove_finder() -> None:
    sys.meta_path[:] = [f for f in sys.meta_path if not importer._is_finder(f)]


@pytest.fixture
def hook_state():
    """Leave the finder installed whatever a test did to it."""
    yield
    remove_finder()
    importer.install()


def test_install_appends_one_finder_at_the_end(hook_state):
    remove_finder()
    importer.install()
    importer.install()
    assert len(finders()) == 1
    assert sys.meta_path[-1] is finders()[0]


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
        "{#python\nif __name__ == '__main__':\n    print('ran', __file__)\n"
        + CLASS
        + "#}\n<p></p>\n",
    )
    result = run("", "-m", "pkg.card", path=tmp_path, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"ran {tmp_path / 'pkg' / 'card.pjx'}"


def test_reload_runs_the_block_again(write: Write, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_RUNS", "0")
    write(
        "pkg/card.pjx",
        "{#python\nimport os\nos.environ['PJX_RUNS'] += 'x'\n"
        + CLASS
        + "#}\n<p></p>\n",
    )
    card = importlib.import_module("pkg.card")
    assert importlib.reload(card) is card
    assert os.environ["PJX_RUNS"] == "0xx"


def refused(write: Write, text: str) -> ImportError:
    path = write("pkg/card.pjx", text)
    with pytest.raises(ImportError) as raised:
        importlib.import_module("pkg.card")
    assert str(path) in str(raised.value)
    assert "pkg.card" not in sys.modules
    return raised.value


def test_a_block_with_no_class_for_the_stem_is_refused(write: Write):
    text = CARD.replace("class Card", "class Other")
    assert ":1: no component class" in str(refused(write, text))


def test_two_classes_for_the_stem_are_refused(write: Write):
    path = write(
        "pkg/http_card.pjx",
        "{#python\nfrom pyjinhx import BaseComponent\n\n\n"
        "class HTTPCard(BaseComponent):\n    pass\n\n\n"
        "class HttpCard(BaseComponent):\n    pass\n#}\n<p></p>\n",
    )
    with pytest.raises(ImportError, match="HTTPCard.*HttpCard") as raised:
        importlib.import_module("pkg.http_card")
    assert f"{path}:9:" in str(raised.value)
    assert "pkg.http_card" not in sys.modules


def test_extra_classes_and_helpers_are_fine(write: Write):
    write(
        "pkg/card.pjx",
        CARD.replace(
            "#}\n",
            "\n\ndef helper():\n    return 1\n\n\nclass Plain:\n    pass\n\n\n"
            "class WideCard(Card):\n    pass\n#}\n",
            1,
        ),
    )
    card = importlib.import_module("pkg.card")
    assert {card.Plain.__name__, card.WideCard.__name__} == {"Plain", "WideCard"}


def test_loaded_document_names_the_module_and_class(write: Write):
    path = write("pkg/card.pjx", CARD)
    assert importer.loaded_document(path) is None
    card = importlib.import_module("pkg.card")
    assert importer.loaded_document(path) == ("pkg.card", card.Card)
    assert importer.loaded_document(str(path)) == ("pkg.card", card.Card)
    assert importer.loaded_document(path.with_name("other.pjx")) is None


def test_loaded_document_forgets_a_refused_file(write: Write):
    path = write("pkg/card.pjx", CARD.replace("class Card", "class Other"))
    with pytest.raises(ImportError):
        importlib.import_module("pkg.card")
    assert importer.loaded_document(path) is None


def test_pickle_and_deepcopy_round_trip(write: Write):
    import copy
    import pickle

    write("pkg/card.pjx", CARD)
    card = importlib.import_module("pkg.card").Card(title="hi")
    assert copy.deepcopy(card) == card
    assert pickle.loads(pickle.dumps(card)) == card


def test_unpickling_in_a_fresh_process_finds_the_class(write: Write, tmp_path: Path):
    import pickle

    write("pkg/__init__.py", "import pyjinhx\n")
    write("pkg/card.pjx", CARD)
    blob = pickle.dumps(importlib.import_module("pkg.card").Card(title="hi"))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pickle, sys; print(pickle.loads(bytes.fromhex(sys.argv[1])).title)",
            blob.hex(),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
    )
    assert result.stdout.strip() == "hi", result.stderr


def test_concurrent_imports_share_one_module(write: Write):
    from concurrent.futures import ThreadPoolExecutor

    write("pkg/card.pjx", CARD)
    with ThreadPoolExecutor(8) as pool:
        modules = list(
            pool.map(lambda _: importlib.import_module("pkg.card"), range(8))
        )
    assert {id(module) for module in modules} == {id(modules[0])}


def test_a_byte_order_mark_does_not_hide_the_block(write: Write):
    path = write("pkg/card.pjx", CARD)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert importlib.import_module("pkg.card").Card.__module__ == "pkg.card"


def test_find_spec_stays_quiet_about_a_malformed_block(write: Write):
    write("pkg/card.pjx", "{#python\nX = 1\n")
    assert importlib.util.find_spec("pkg.card") is not None
    with pytest.raises(SyntaxError, match="never closed"):
        importlib.import_module("pkg.card")


def test_find_spec_stays_quiet_about_a_file_that_is_not_utf8(write: Write):
    path = write("pkg/card.pjx", "")
    path.write_bytes(b"\xff\xfe{#python\n")
    assert importlib.util.find_spec("pkg.card") is None
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pkg.card")


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_find_spec_stays_quiet_about_an_unreadable_file(write: Write):
    path = write("pkg/card.pjx", CARD)
    path.chmod(0)
    try:
        assert importlib.util.find_spec("pkg.card") is None
    finally:
        path.chmod(0o644)


def test_find_spec_declines_a_spaced_opener(write: Write):
    write("pkg/card.pjx", "{# python\nX = 1\n#}\n<p></p>\n")
    assert importlib.util.find_spec("pkg.card") is None


def test_a_sibling_package_directory_wins_too(write: Write):
    """Known: the ordinary path search finds `card/` first; a later task
    refuses the pair at setup."""
    write("pkg/card/other.py", "")
    write("pkg/card.pjx", CARD)
    assert not hasattr(importlib.import_module("pkg.card"), "Card")


def test_the_same_file_under_a_second_name_is_refused(
    write: Write, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = write("pkg/card.pjx", CARD)
    monkeypatch.syspath_prepend(str(tmp_path / "pkg"))
    importlib.import_module("pkg.card")
    with pytest.raises(ImportError, match="pkg.card") as raised:
        importlib.import_module("card")
    assert str(path) in str(raised.value)
    assert "card" not in sys.modules


def test_loaded_document_checks_the_module_is_still_that_file(write: Write):
    path = write("pkg/card.pjx", CARD)
    importlib.import_module("pkg.card")
    sys.modules["pkg.card"] = sys.modules["pkg"]
    assert importer.loaded_document(path) is None


def test_install_survives_a_reloaded_importer(hook_state):
    remove_finder()
    importer.install()
    importlib.reload(importer)
    importer.install()
    assert [type(f).__name__ for f in sys.meta_path].count("PjxFinder") == 1


def test_module_name_is_the_path_below_the_deepest_search_entry(tmp_path: Path):
    path = tmp_path / "app" / "ui" / "card.pjx"
    assert sfc.module_name_for(path, [str(tmp_path)]) == "app.ui.card"
    deeper = [str(tmp_path), str(tmp_path / "app")]
    assert sfc.module_name_for(path, deeper) == "ui.card"


def test_module_name_is_none_when_no_entry_holds_the_file(tmp_path: Path):
    path = tmp_path / "app" / "card.pjx"
    assert sfc.module_name_for(path, [str(tmp_path / "other")]) is None


def test_module_name_is_none_for_a_directory_that_is_not_a_name(tmp_path: Path):
    path = tmp_path / "my-app" / "card.pjx"
    assert sfc.module_name_for(path, [str(tmp_path)]) is None


def test_module_name_reads_an_empty_entry_as_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    assert sfc.module_name_for(tmp_path / "card.pjx", [""]) == "card"


def test_module_name_walks_up_the_packages_when_the_top_is_on_the_path(
    tmp_path: Path,
):
    (tmp_path / "site" / "comp").mkdir(parents=True)
    (tmp_path / "site" / "__init__.py").write_text("")
    (tmp_path / "site" / "comp" / "__init__.py").write_text("")
    path = tmp_path / "site" / "comp" / "badge.pjx"
    entries = [str(tmp_path / "site" / "comp"), str(tmp_path)]
    assert sfc.module_name_for(path, entries) == "site.comp.badge"


def test_module_name_without_a_search_path_is_the_package_walk(tmp_path: Path):
    (tmp_path / "site" / "comp").mkdir(parents=True)
    (tmp_path / "site" / "__init__.py").write_text("")
    (tmp_path / "site" / "comp" / "__init__.py").write_text("")
    assert sfc.module_name_for(tmp_path / "site" / "comp" / "badge.pjx") == (
        "site.comp.badge"
    )
    assert sfc.module_name_for(tmp_path / "loose" / "badge.pjx") == "badge"


def test_module_name_keeps_a_symlinked_directory_as_the_app_spells_it(
    tmp_path: Path,
):
    real = tmp_path / "real" / "ui"
    real.mkdir(parents=True)
    (tmp_path / "proj" / "app").mkdir(parents=True)
    (tmp_path / "proj" / "app" / "__init__.py").write_text("")
    (tmp_path / "proj" / "app" / "ui").symlink_to(real)
    path = tmp_path / "proj" / "app" / "ui" / "card.pjx"
    assert sfc.module_name_for(path, [str(tmp_path / "proj")]) == "app.ui.card"


def test_module_name_falls_back_to_the_resolved_path(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    assert sfc.module_name_for(tmp_path / "link" / "card.pjx", [str(real)]) == "card"


def test_import_document_imports_once_and_returns_the_module(write: Write):
    write("pkg/log.py", "runs = []\n")
    path = write(
        "pkg/card.pjx",
        "{#python\nfrom pkg.log import runs\nruns.append(1)\n"
        + CLASS
        + "#}\n<p></p>\n",
    )
    first = importer.import_document(path)
    assert importer.import_document(path) is first
    assert importlib.import_module("pkg.log").runs == [1]


def test_import_document_returns_a_module_the_test_imported(write: Write):
    path = write("pkg/card.pjx", CARD)
    module = importlib.import_module("pkg.card")
    assert importer.import_document(path) is module


def test_import_document_returns_a_module_loaded_under_another_name(
    write: Write, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = write("pkg/card.pjx", CARD)
    monkeypatch.syspath_prepend(str(tmp_path / "pkg"))
    module = importlib.import_module("pkg.card")
    assert importer.import_document(path) is module
    assert "card" not in sys.modules


def test_import_document_refuses_a_sibling_py_module(write: Write):
    path = write("pkg/card.pjx", CARD)
    shadow = write("pkg/card.py", "")
    with pytest.raises(ImportError) as raised:
        importer.import_document(path)
    assert str(path) in str(raised.value)
    assert str(shadow) in str(raised.value)


def test_import_document_refuses_a_sibling_package_directory(
    write: Write, tmp_path: Path
):
    path = write("pkg/card.pjx", CARD)
    write("pkg/card/other.py", "")
    with pytest.raises(ImportError) as raised:
        importer.import_document(path)
    assert str(path) in str(raised.value)
    assert str(tmp_path / "pkg" / "card") in str(raised.value)


def test_import_document_refuses_a_namespace_directory(write: Write, tmp_path: Path):
    path = write("pkg/card.pjx", CARD)
    (tmp_path / "pkg" / "card").mkdir()
    importlib.invalidate_caches()
    with pytest.raises(ImportError) as raised:
        importer.import_document(path)
    assert str(path) in str(raised.value)
    assert str(tmp_path / "pkg" / "card") in str(raised.value)


def test_import_document_outside_the_search_path_says_how_to_fix_it(
    write: Write, tmp_path: Path
):
    elsewhere = tmp_path.parent / f"{tmp_path.name}_elsewhere" / "card.pjx"
    elsewhere.parent.mkdir()
    elsewhere.write_text(CARD, encoding="utf-8")
    with pytest.raises(ImportError, match=r"sys\.path") as raised:
        importer.import_document(elsewhere)
    assert str(elsewhere) in str(raised.value)
    assert "__init__.py" in str(raised.value)
    assert "before setup()" in str(raised.value)


def test_import_document_names_a_parent_package_that_something_else_shadows(
    write: Write, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    other = tmp_path / "elsewhere"
    (other / "widgets").mkdir(parents=True)
    (other / "widgets" / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(other))
    path = write("widgets/chip.pjx", CARD)
    with pytest.raises(ImportError, match="shadowed") as raised:
        importer.import_document(path)
    assert str(path) in str(raised.value)
    assert str(other / "widgets") in str(raised.value)


def test_import_document_does_not_hide_a_missing_module_inside_the_block(
    write: Write,
):
    path = write("pkg/card.pjx", "{#python\nimport nowhere_at_all\n#}\n")
    with pytest.raises(ModuleNotFoundError, match="nowhere_at_all"):
        importer.import_document(path)


def test_import_document_lets_a_block_error_through_with_its_line(write: Write):
    path = write("pkg/card.pjx", "{#python\nraise RuntimeError('boom')\n#}\n")
    with pytest.raises(RuntimeError) as raised:
        importer.import_document(path)
    frames = traceback.extract_tb(raised.value.__traceback__)
    assert (str(path), 2) in {(f.filename, f.lineno) for f in frames}


def test_find_spec_declines_a_prose_comment_that_starts_with_python(write: Write):
    write("pkg/note.pjx", "{# python helpers below #}\n{#python is nice #}\n<p></p>\n")
    assert importlib.util.find_spec("pkg.note") is None


def test_find_spec_declines_an_example_inside_raw(write: Write):
    write("pkg/guide.pjx", "{% raw %}\n{#python\nx = 1\n#}\n{% endraw %}\n")
    assert importlib.util.find_spec("pkg.guide") is None


def test_importing_pyjinhx_does_not_load_importlib_abc():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, pyjinhx; print('importlib.abc' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_find_spec_does_not_open_files_that_are_not_there(
    write: Write, monkeypatch: pytest.MonkeyPatch
):
    def unexpected(*args, **kwargs):
        raise AssertionError("opened a file")

    monkeypatch.setattr(Path, "read_text", unexpected)
    assert importer.PjxFinder().find_spec("pkg.no_such_module", None) is None


@pytest.mark.parametrize("text", [CARD, "{#python\nX = 1\n#}\n<p></p>\n"])
def test_the_loader_reads_the_file_once_per_import(
    write: Write, monkeypatch: pytest.MonkeyPatch, text: str
):
    write("pkg/card.pjx", text)
    reads = []
    original = importer.PjxLoader.get_data

    def counting(self, path):
        reads.append(path)
        return original(self, path)

    monkeypatch.setattr(importer.PjxLoader, "get_data", counting)
    try:
        importlib.import_module("pkg.card")
    except ImportError:
        pass
    assert len(reads) == 1
