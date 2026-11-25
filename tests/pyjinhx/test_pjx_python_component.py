"""A ``.pjx`` document that holds its class: binding, refusals and rendering."""

import importlib
import logging
import os
import subprocess
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

import jinja2
import pytest

from pyjinhx import assets, discovery
from pyjinhx._component import all_component_classes
from pyjinhx.assets import asset_token
from pyjinhx.render_cache import render_cache_key
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, accumulate_assets, request_scope
from pyjinhx.sfc import BlockSyntaxError
from pyjinhx.template_blocks import InlineAsset

Write = Callable[[str, str], Path]

CARD = """\
{#python
from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str = ""
#}
<div>{{ title }}</div>
"""

SPLIT_CARD_PY = """\
from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str = ""
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


@pytest.fixture(autouse=True)
def reset_registry():
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def load(name: str):
    return importlib.import_module(name)


def test_the_descriptor_points_at_the_pjx_itself(write: Write):
    path = write("pkg/card.pjx", CARD)
    card = load("pkg.card").Card
    descriptor = card.__pjx_descriptor__
    assert descriptor.template_path == path
    assert descriptor.inline_class is None
    assert descriptor.provenance["template"] is card


def test_the_walk_probes_as_often_as_for_a_split_component(
    write: Write, monkeypatch: pytest.MonkeyPatch
):
    write("pkg/card.pjx", CARD)
    write("pkg/plain.py", SPLIT_CARD_PY.replace("Card", "Plain"))
    write("pkg/plain.pjx", "<div></div>")
    probed: list[Path] = []
    real = Path.is_file

    def counting(self, *args, **kwargs):
        probed.append(self)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "is_file", counting)
    load("pkg.card")
    in_block = [p for p in probed if p.suffix == ".pjx"]
    probed.clear()
    load("pkg.plain")
    split = [p for p in probed if p.suffix == ".pjx"]
    assert len(in_block) == len(split)


def test_rendering_leaves_no_blank_line_where_the_block_was(write: Write):
    write("pkg/card.pjx", CARD)
    assert load("pkg.card").Card(title="a").render() == "<div>a</div>"


def test_rendering_matches_the_same_component_written_split(write: Write):
    write("pkg/card.pjx", CARD)
    write("pkg/split/__init__.py", "")
    write("pkg/split/card.py", SPLIT_CARD_PY)
    write("pkg/split/card.pjx", "<div>{{ title }}</div>\n")
    block = load("pkg.card").Card(id="x", title="a").render()
    split = load("pkg.split.card").Card(id="x", title="a").render()
    assert block == split


def test_the_block_never_reaches_the_output(write: Write):
    write("pkg/card.pjx", CARD)
    out = load("pkg.card").Card(title="a").render()
    assert "python" not in out and "BaseComponent" not in out


def test_a_template_error_names_the_pjx_line(write: Write):
    path = write(
        "pkg/card.pjx",
        "{#python\nfrom pyjinhx import BaseComponent\n\n\n"
        "class Card(BaseComponent):\n    pass\n#}\n<div>\n  {{ nothing.here }}\n</div>\n",
    )
    with pytest.raises(jinja2.UndefinedError) as caught:
        load("pkg.card").Card().render()
    frames = traceback.extract_tb(caught.value.__traceback__)
    frame = next(f for f in frames if "template code" in f.name)
    assert frame.filename == str(path)
    assert frame.lineno == 9


def test_inline_css_and_js_ship_after_a_sibling_css(write: Write):
    write("pkg/card.css", ".sibling { color: red; }")
    write(
        "pkg/card.pjx",
        CARD + "{#css\n.card { color: blue; }\n#}\n{#js\nconsole.log('card');\n#}\n",
    )
    card = load("pkg.card").Card
    sibling, inline_css = card.__pjx_descriptor__.css_paths
    assert sibling.name == "card.css"
    assert isinstance(inline_css, InlineAsset)
    assert inline_css.read_text() == ".card { color: blue; }"
    (inline_js,) = card.__pjx_descriptor__.js_paths
    assert isinstance(inline_js, InlineAsset)
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    out = render(card(), session)
    assert f'data-pjx-asset="{asset_token(inline_css)}"' in out
    assert out.count("console.log('card')") == 1
    assert "{#" not in out


def test_a_tag_expands_to_a_block_component(write: Write):
    write("pkg/card.pjx", CARD)
    write(
        "pkg/shelf.pjx",
        "{#python\nfrom pyjinhx import BaseComponent\n\n\n"
        'class Shelf(BaseComponent):\n    pass\n#}\n<section><Card title="hi"/></section>\n',
    )
    card = load("pkg.card").Card
    shelf = load("pkg.shelf").Shelf
    discovery.build_registry(None, [card, shelf])
    assert shelf().render() == "<section><div>hi</div></section>"


def test_a_second_class_in_the_block_renders_the_parents_document(write: Write):
    write(
        "pkg/card.pjx",
        CARD.replace("#}", "\n\nclass WideCard(Card):\n    pass\n#}", 1),
    )
    wide = load("pkg.card").WideCard
    assert wide(title="w").render() == "<div>w</div>"
    assert wide.__pjx_descriptor__.provenance["template"] is load("pkg.card").Card


def test_a_py_subclass_of_a_block_class_renders_the_parents_document(write: Write):
    write("pkg/card.pjx", CARD)
    write(
        "pkg/tall.py",
        "from pkg.card import Card\n\n\nclass TallCard(Card):\n    pass\n",
    )
    assert load("pkg.tall").TallCard(title="t").render() == "<div>t</div>"


def test_a_block_class_subclassing_another_block_class(write: Write):
    write("pkg/card.pjx", CARD)
    write(
        "pkg/plain_card.pjx",
        "{#python\nfrom pkg.card import Card\n\n\nclass PlainCard(Card):\n    pass\n#}\n"
        "<b>plain</b>\n",
    )
    plain = load("pkg.plain_card").PlainCard
    assert plain().render() == "<b>plain</b>"
    inherits = write(
        "pkg/bare.pjx",
        "{#python\nfrom pkg.card import Card\n\n\nclass Bare(Card):\n    pass\n#}\n",
    )
    assert inherits.exists()


def test_a_reactive_block_component_keeps_its_react_keys(write: Write):
    write(
        "pkg/counter.pjx",
        "{#python\nfrom pyjinhx import ReactiveComponent\n\n\n"
        'class Counter(ReactiveComponent, react={"todos"}):\n'
        "    remaining: int = 0\n\n"
        "    @classmethod\n    def load(cls) -> 'Counter':\n"
        "        return cls(remaining=3)\n#}\n"
        '<div class="counter">{{ remaining }} left</div>\n',
    )
    counter = load("pkg.counter").Counter
    assert counter._pjx_react_keys == ("todos",)
    with request_scope():
        assert "3 left</div>" in counter.load().render()


def test_the_render_cache_key_follows_the_pjx_mtime(write: Write):
    path = write("pkg/card.pjx", CARD)
    card = load("pkg.card").Card(id="c")
    before = render_cache_key(card)
    assert before.startswith("pkg.card.Card:")
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 10))
    assert render_cache_key(card) != before


def refusal(name: str) -> pytest.ExceptionInfo[TypeError]:
    with pytest.raises(TypeError) as caught:
        load(name)
    return caught


def test_a_def_header_beside_a_block_is_refused(write: Write):
    path = write("pkg/card.pjx", CARD.replace("<div>", "{#def title: str #}\n<div>"))
    message = str(refusal("pkg.card").value)
    assert message.startswith(f"{path}:8: ")
    assert "{#def#} header" in message


def test_a_legacy_def_header_beside_a_block_is_refused(write: Write):
    path = write("pkg/card.pjx", "{# def title: str #}\n" + CARD)
    assert str(refusal("pkg.card").value).startswith(f"{path}:1: ")


def test_a_document_with_no_markup_is_refused(write: Write):
    path = write(
        "pkg/card.pjx",
        CARD.split("#}")[0] + "#}\n{# a note #}\n\n{#css\n.a { }\n#}\n",
    )
    message = str(refusal("pkg.card").value)
    assert message.startswith(f"{path}:1: ")
    assert "no markup" in message


def test_markup_that_is_only_a_tag_still_counts(write: Write):
    write(
        "pkg/card.pjx",
        CARD.split("#}")[0] + "#}\n{% if title %}<i>{{ title }}</i>{% endif %}\n",
    )
    assert load("pkg.card").Card(title="x").render() == "<i>x</i>"


def test_a_sibling_py_class_beside_a_block_document_is_refused(write: Write):
    py = write("pkg/card.py", SPLIT_CARD_PY)
    pjx = write("pkg/card.pjx", CARD)
    message = str(refusal("pkg.card").value)
    assert message.startswith(f"{pjx}:1: ")
    assert str(py) in message and "remove one" in message


def test_a_split_pair_without_a_block_is_not_refused(write: Write):
    write("pkg/card.py", SPLIT_CARD_PY)
    write("pkg/card.pjx", "{#def title: str #}\n<div>{{ title }}</div>\n")
    assert load("pkg.card").Card(title="a").render() == "<div>a</div>"


def test_an_inline_template_in_a_block_class_is_refused(write: Write):
    path = write(
        "pkg/card.pjx",
        "{#python\nfrom pyjinhx import BaseComponent\n\n\n"
        'class Card(BaseComponent):\n    template = "<p></p>"\n#}\n<div></div>\n',
    )
    message = str(refusal("pkg.card").value)
    assert message.startswith(f"{path}:5: Card assigns `template`")


def registered(module_name: str) -> list[type]:
    return [cls for cls in all_component_classes() if cls.__module__ == module_name]


def test_a_class_from_a_refused_import_is_not_registered(write: Write):
    write(
        "pkg/card.pjx",
        "{#python\nfrom pyjinhx import BaseComponent\n\n\n"
        "class Other(BaseComponent):\n    pass\n#}\n<div></div>\n",
    )
    with pytest.raises(ImportError):
        load("pkg.card")
    assert registered("pkg.card") == []


def test_a_reloaded_document_registers_only_its_new_class(write: Write):
    write("pkg/card.pjx", CARD)
    module = load("pkg.card")
    old = module.Card
    importlib.reload(module)
    assert module.Card is not old
    assert registered("pkg.card") == [module.Card]


def test_a_live_block_class_is_registered(write: Write):
    write("pkg/card.pjx", CARD)
    module = load("pkg.card")
    assert module.Card in all_component_classes()


def test_a_class_whose_module_is_gone_is_not_registered(write: Write):
    write("pkg/card.py", SPLIT_CARD_PY)
    write("pkg/card.pjx", "<div>{{ title }}</div>\n")
    card = load("pkg.card").Card
    del sys.modules["pkg.card"]
    assert card not in all_component_classes()


def test_python_dash_m_binds_the_class_and_leaves_it_unregistered(
    write: Write, tmp_path: Path
):
    write("pkg/__init__.py", "import pyjinhx\n")
    path = write(
        "pkg/card.pjx",
        CARD.replace(
            "#}",
            "\nif __name__ == '__main__':\n"
            "    from pyjinhx._component import all_component_classes\n"
            "    print(Card.__pjx_descriptor__.template_path)\n"
            "    print(Card(title='a').render())\n"
            "    print(Card in all_component_classes())\n#}",
            1,
        ),
    )
    result = subprocess.run(
        [sys.executable, "-m", "pkg.card"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split("\n")[:3] == [str(path), "<div>a</div>", "False"]


def test_a_reloaded_py_module_registers_only_its_new_class(write: Write):
    write("pkg/card.py", SPLIT_CARD_PY)
    write("pkg/card.pjx", "<div>{{ title }}</div>\n")
    module = load("pkg.card")
    old = module.Card
    importlib.reload(module)
    assert registered("pkg.card") == [module.Card]
    assert old not in all_component_classes()


def test_a_factory_built_and_a_nested_block_class_are_registered(write: Write):
    write(
        "pkg/card.pjx",
        CARD.replace(
            "#}",
            "\n\ndef _make():\n    class Small(Card):\n        pass\n"
            "    return Small\n\n\nSmall = _make()\n\n\n"
            "class Outer(BaseComponent):\n    class Inner(Card):\n        pass\n#}",
            1,
        ),
    )
    module = load("pkg.card")
    live = all_component_classes()
    assert module.Small in live
    assert module.Outer.Inner in live


def test_dev_skips_a_reloaded_documents_old_class(write: Write):
    write("pkg/card.pjx", CARD)
    module = load("pkg.card")
    old = module.Card
    importlib.reload(module)
    assert old not in all_component_classes()


def test_assets_skip_a_refused_imports_classes(write: Write):
    write("pkg/other.css", ".other { }")
    write(
        "pkg/card.pjx",
        "{#python\nfrom pyjinhx import BaseComponent\n\n\n"
        "class Other(BaseComponent):\n    pass\n#}\n<div></div>\n",
    )
    with pytest.raises(ImportError):
        load("pkg.card")
    assert not any(path.name == "other.css" for path in assets.all_assets()[0])


def test_a_malformed_block_beside_a_py_class_names_the_class(write: Write):
    path = write("pkg/card.py", SPLIT_CARD_PY)
    write("pkg/card.pjx", "<div>\n  {#python\n  x = 1\n  #}\n</div>\n")
    with pytest.raises(BlockSyntaxError) as caught:
        load("pkg.card")
    error = caught.value
    assert error.code == "opener-not-at-line-start"
    assert error.lineno == 2
    assert error.filename == str(path.with_suffix(".pjx"))
    assert "Card" in str(error)


def test_a_class_with_two_component_bases_is_listed_once(write: Write):
    write(
        "pkg/shapes.py",
        "from pyjinhx import BaseComponent\n\n\n"
        "class Left(BaseComponent):\n    pass\n\n\n"
        "class Right(BaseComponent):\n    pass\n\n\n"
        "class Both(Left, Right):\n    pass\n",
    )
    module = load("pkg.shapes")
    assert all_component_classes().count(module.Both) == 1


def edit(path: Path, old: str, new: str) -> None:
    """Rewrite ``path`` with ``old`` replaced and its mtime moved on."""
    stat = path.stat()
    path.write_text(path.read_text().replace(old, new), encoding="utf-8")
    os.utime(path, (stat.st_atime + 10, stat.st_mtime + 10))


def block_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "{#python" in r.getMessage()]


def test_a_markup_edit_applies_live_and_does_not_warn(
    write: Write, caplog: pytest.LogCaptureFixture
):
    path = write("pkg/card.pjx", CARD)
    card = load("pkg.card").Card
    assert card(title="a").render() == "<div>a</div>"
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        edit(path, "<div>", "<p>")
        edit(path, "</div>", "</p>")
        assert card(title="a").render() == "<p>a</p>"
    assert block_warnings(caplog) == []


def test_a_block_edit_warns_once_per_change_and_keeps_the_imported_class(
    write: Write, caplog: pytest.LogCaptureFixture
):
    path = write("pkg/card.pjx", CARD)
    card = load("pkg.card").Card
    card(title="a").render()
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        edit(path, 'title: str = ""', 'title: str = "x"')
        assert card(title="a").render() == "<div>a</div>"
        assert block_warnings(caplog) == [
            f"{path}: the {{#python block changed; restart the process to load it"
        ]
        edit(path, "<div>", "<p>")
        card(title="a").render()
        assert len(block_warnings(caplog)) == 1
        edit(path, 'title: str = "x"', 'title: str = "y"')
        card(title="a").render()
        assert len(block_warnings(caplog)) == 2


def test_a_block_never_imported_through_the_hook_does_not_warn(
    write: Write, caplog: pytest.LogCaptureFixture
):
    path = write("pkg/card.pjx", CARD)
    from pyjinhx.session import AbsolutePathLoader

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        AbsolutePathLoader().get_source(jinja2.Environment(), str(path))
        edit(path, "title", "name")
        AbsolutePathLoader().get_source(jinja2.Environment(), str(path))
    assert block_warnings(caplog) == []


def test_an_unedited_document_with_crlf_line_ends_does_not_warn(
    write: Write, caplog: pytest.LogCaptureFixture
):
    path = write("pkg/card.pjx", CARD)
    path.write_bytes(CARD.replace("\n", "\r\n").encode())
    card = load("pkg.card").Card
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        assert card(title="a").render() == "<div>a</div>"
        edit(path, "<div>", "<p>")
        card(title="a").render()
    assert block_warnings(caplog) == []
