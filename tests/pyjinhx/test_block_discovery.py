"""Discovery of ``.pjx`` documents that hold a ``{#python`` block: imported
eagerly by `setup()`, lazily on a tag miss, and never twice."""

import importlib
import sys
import threading
import traceback
import types
from pathlib import Path

import pytest

from pyjinhx import BaseComponent
from pyjinhx.components import discovery, importer
from pyjinhx.components.base import all_component_classes
from pyjinhx.components.classless import component, register_document
from pyjinhx.config import setup, shutdown_pyjinhx
from pyjinhx.rendering.pipeline import render
from tests.pyjinhx.conftest import Write

CARD = """\
{#python
from pkg.log import runs
from pyjinhx import BaseComponent

runs.append("plaque")


class Plaque(BaseComponent):
    title: str = ""
#}
<div>{{ title }}</div>
"""


@pytest.fixture(autouse=True)
def clean_registry():
    shutdown_pyjinhx()
    discovery.build_registry(None, [])
    yield
    shutdown_pyjinhx()
    discovery.build_registry(None, [])


@pytest.fixture
def root(write: Write, tmp_path: Path) -> Path:
    write("pkg/log.py", "runs = []\n")
    return tmp_path / "pkg"


def runs() -> list[str]:
    return importlib.import_module("pkg.log").runs


def test_setup_imports_a_document_nobody_imported(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD)
    setup(components_root=root)
    plaque = discovery.get_class("plaque")
    assert plaque is not None and plaque.__module__ == "pkg.plaque"
    assert plaque in all_component_classes()
    assert plaque in BaseComponent.__subclasses__()


def test_setup_twice_runs_each_block_once(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD)
    setup(components_root=root)
    setup(components_root=root)
    assert runs() == ["plaque"]
    assert discovery.get_class("plaque") is sys.modules["pkg.plaque"].Plaque


def test_setup_leaves_a_document_the_app_imported_alone(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD)
    importlib.import_module("pkg.plaque")
    setup(components_root=root)
    assert runs() == ["plaque"]
    assert discovery.get_class("plaque") is sys.modules["pkg.plaque"].Plaque


def test_setup_before_the_app_imports_anything(write: Write, root: Path):
    write("pkg/helper.py", "VALUE = 3\n")
    write(
        "pkg/plaque.pjx",
        "{#python\nfrom pkg.helper import VALUE\nfrom pyjinhx import BaseComponent\n\n\n"
        "class Plaque(BaseComponent):\n    n: int = VALUE\n#}\n<i>{{ n }}</i>\n",
    )
    setup(components_root=root)
    assert "<i>3</i>" in render(sys.modules["pkg.plaque"].Plaque())


def test_a_block_may_ask_for_a_header_only_sibling_while_setup_imports(
    write: Write, root: Path
):
    write("pkg/ledgerline.pjx", "{#def title: str = '' #}<b>{{ title }}</b>")
    write(
        "pkg/plaque.pjx",
        "{#python\nfrom pyjinhx import BaseComponent, component\n\n"
        'Ledgerline = component("Ledgerline")\n\n\nclass Plaque(BaseComponent):\n    pass\n#}\n'
        "<Ledgerline title='x'/>\n",
    )
    setup(components_root=root)
    assert "<b>x</b>" in render(discovery.get_class("plaque")())  # pyright: ignore


def test_a_block_error_fails_setup_with_the_pjx_line(write: Write, root: Path):
    path = write(
        "pkg/plaque.pjx", "{#python\nraise RuntimeError('boom')\n#}\n<p></p>\n"
    )
    with pytest.raises(RuntimeError, match="boom") as raised:
        setup(components_root=root)
    frames = traceback.extract_tb(raised.value.__traceback__)
    assert (str(path), 2) in {(f.filename, f.lineno) for f in frames}


def test_a_document_with_a_misnamed_class_fails_setup_naming_the_file(
    write: Write, root: Path
):
    path = write("pkg/plaque.pjx", CARD.replace("class Plaque", "class Other"))
    with pytest.raises(ImportError, match="named for 'plaque'") as raised:
        setup(components_root=root)
    assert str(path) in str(raised.value)


def test_a_namespace_directory_shadowing_a_document_fails_setup(
    write: Write, root: Path
):
    path = write("pkg/plaque.pjx", CARD)
    (root / "plaque").mkdir()
    importlib.invalidate_caches()
    with pytest.raises(ImportError) as raised:
        setup(components_root=root)
    assert str(path) in str(raised.value) and str(root / "plaque") in str(raised.value)


def test_a_document_outside_sys_path_fails_setup_with_the_fix(tmp_path: Path):
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    path = lonely / "plaque.pjx"
    path.write_text(CARD, encoding="utf-8")
    with pytest.raises(ImportError, match=r"sys\.path") as raised:
        setup(components_root=lonely)
    assert str(path) in str(raised.value)


def test_an_indented_opener_is_a_plain_comment(write: Write, root: Path):
    write("pkg/ledgerline.pjx", "{#def #}<p></p>\n  {#python\nX = 1\n#}\n")
    write("pkg/example.pjx", "{#def #}<pre>\n    {#python\n    x = 1\n    #}\n</pre>\n")
    setup(components_root=root)
    assert "pkg.ledgerline" not in sys.modules
    assert "pkg.example" not in sys.modules


def test_two_blocks_at_the_line_start_still_fail_setup(write: Write, root: Path):
    path = write("pkg/plaque.pjx", CARD + "{#python\nX = 1\n#}\n")
    with pytest.raises(SyntaxError) as raised:
        setup(components_root=root)
    assert raised.value.filename == str(path)
    assert "line 1 opens a {#python block" in str(raised.value.msg)


def test_a_column_zero_example_in_prose_is_a_document_and_says_why(
    write: Write, root: Path
):
    path = write("pkg/guide.pjx", "<pre>\n{#python\nx = 1\n#}\n</pre>\n")
    with pytest.raises(ImportError, match="named for 'guide'") as raised:
        setup(components_root=root)
    assert str(path) in str(raised.value)


def test_a_spaced_opener_is_a_comment_not_a_document(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD.replace("{#python", "{# python", 1))
    setup(components_root=root)
    assert "pkg.plaque" not in sys.modules


def test_a_header_only_template_and_a_plain_one_are_untouched(write: Write, root: Path):
    write("pkg/ledgerline.pjx", "{#def title: str = '' #}<b>{{ title }}</b>")
    write("pkg/bareplain.pjx", "<p>bareplain</p>")
    setup(components_root=root)
    assert "<b>x</b>" in render(component("Ledgerline")(title="x"))  # pyright: ignore[reportCallIssue]
    assert discovery.get_class("bareplain") is None


def test_a_package_that_calls_setup_while_it_is_imported(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD)
    write(
        "pkg/__init__.py",
        f"from pyjinhx import setup\nsetup(components_root={str(root)!r})\n",
    )
    for name in [n for n in sys.modules if n == "pkg" or n.startswith("pkg.")]:
        del sys.modules[name]
    setup(components_root=root)
    assert runs() == ["plaque"]
    assert discovery.get_class("plaque") is sys.modules["pkg.plaque"].Plaque


def test_a_tag_miss_imports_the_document(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD)
    write("pkg/leafsheet.pjx", '{#def #}<main><Plaque title="x"/></main>')
    discovery.build_registry(root, [])
    html = render(component("Leafsheet")())
    assert "<div>x</div>" in html
    plaque = component("Plaque")
    assert plaque is sys.modules["pkg.plaque"].Plaque
    assert discovery.get_class("plaque") is plaque
    assert runs() == ["plaque"]


def test_a_block_document_is_no_longer_an_orphan_once_imported(
    write: Write, root: Path
):
    write("pkg/plaque.pjx", CARD)
    discovery.build_registry(root, [])
    assert discovery.get_orphan_templates("plaque")
    component("Plaque")
    assert not discovery.get_orphan_templates("plaque")


def test_a_tag_miss_imports_a_document_once_across_threads(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD)
    write("pkg/leafsheet.pjx", '{#def #}<main><Plaque title="x"/></main>')
    discovery.build_registry(root, [])
    page = component("Leafsheet")
    htmls: list[str] = []
    gate = threading.Barrier(8)

    def go() -> None:
        gate.wait()
        htmls.append(render(page()))

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(htmls) == 8 and all("<div>x</div>" in h for h in htmls)
    assert runs() == ["plaque"]
    assert sum(c.__name__ == "Plaque" for c in all_component_classes()) == 1


def test_a_lazy_import_error_names_the_file(write: Write, root: Path):
    path = write(
        "pkg/plaque.pjx", "{#python\nraise RuntimeError('boom')\n#}\n<p></p>\n"
    )
    discovery.build_registry(root, [])
    with pytest.raises(RuntimeError) as raised:
        component("Plaque")
    frames = traceback.extract_tb(raised.value.__traceback__)
    assert str(path) in {f.filename for f in frames}


def test_the_hook_is_what_found_the_document(write: Write, root: Path):
    write("pkg/plaque.pjx", CARD)
    setup(components_root=root)
    loaded = importer.loaded_document(root / "plaque.pjx")
    assert loaded is not None and loaded[0] == "pkg.plaque"


def test_a_document_replaces_the_class_built_from_the_same_file_earlier(
    write: Write, root: Path
):
    path = write("pkg/plaque.pjx", "{#def title: str = '' #}<i>{{ title }}</i>\n")
    setup(components_root=root)
    built = component("Plaque")
    assert built.__module__.startswith("pyjinhx._classless")
    path.write_text(CARD, encoding="utf-8")
    setup(components_root=root)
    assert discovery.get_class("plaque") is sys.modules["pkg.plaque"].Plaque
    assert component("Plaque") is sys.modules["pkg.plaque"].Plaque
    assert built not in all_component_classes()


def test_a_module_another_loader_made_is_refused_not_ignored(write: Write, root: Path):
    path = write("pkg/plaque.pjx", CARD)
    stranger = types.ModuleType("pkg.plaque")
    stranger.__file__ = str(path)
    sys.modules["pkg.plaque"] = stranger
    with pytest.raises(ImportError, match="not loaded as a document") as raised:
        register_document(path)
    assert str(path) in str(raised.value)


def test_a_line_start_prose_comment_is_not_a_document(write: Write, root: Path):
    write(
        "pkg/ledgerline.pjx",
        "{# python helpers below #}\n{#python is nice #}\n<p></p>\n",
    )
    setup(components_root=root)
    assert "pkg.ledgerline" not in sys.modules


def test_an_example_inside_raw_is_not_a_document(write: Write, root: Path):
    write("pkg/guide.pjx", "{% raw %}\n{#python\nx = 1\n#}\n{% endraw %}\n")
    setup(components_root=root)
    assert "pkg.guide" not in sys.modules


def test_an_indented_opener_is_a_comment_in_a_plain_template(write: Write, root: Path):
    write(
        "pkg/doc_sample.pjx",
        "{#def label: str = 'x' #}\n<div>\n<pre>\n  {#python\n  x = 1\n  #}\n</pre>\n"
        "<p>{{ label }}</p>\n</div>\n",
    )
    setup(components_root=root)
    assert "<p>hi</p>" in component("DocSample")(label="hi").render()
