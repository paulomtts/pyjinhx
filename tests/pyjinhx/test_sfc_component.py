"""Tests for components that carry their template inline, in this very file."""

import importlib.util
import logging
import os
import pickle
import sys
import traceback
import warnings
from pathlib import Path

import jinja2
import pytest
from pydantic import field_validator

from pyjinhx import BaseComponent, discovery
from pyjinhx.assets import asset_token
from pyjinhx.render_cache import render_cache_key
from pyjinhx.rendering import render
from pyjinhx.session import (
    AbsolutePathLoader,
    RenderSession,
    accumulate_assets,
    request_scope,
)
from pyjinhx.template_blocks import InlineAsset

THIS_FILE = Path(__file__)


def _shout(text: str) -> str:
    return text.upper()


def line_of(text: str) -> int:
    """The 1-based line of this file where ``text`` first appears."""
    lines = THIS_FILE.read_text(encoding="utf-8").splitlines()
    return next(number for number, line in enumerate(lines, 1) if text in line)


class Chip(BaseComponent):
    label: str

    template = """
    <span class="chip">{{ label }}</span>
    """


class LoudChip(Chip):
    pass


class QuietChip(Chip):
    template = "<small>{{ label }}</small>"


class ChipRow(BaseComponent):
    template = """
    <div class="row"><Chip label="one"/><Chip label="two"/></div>
    """


class Price(BaseComponent):
    """A full class: validator, computed property, factory, module helper."""

    cents: int
    currency: str = "eur"

    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return _shout(value)

    @property
    def amount(self) -> str:
        return f"{self.cents / 100:.2f}"

    @classmethod
    def free(cls) -> "Price":
        return cls(cents=0, currency="eur")

    template = """
    <data value="{{ cents }}">{{ currency }}</data>
    """


class BrokenSyntax(BaseComponent):
    template = """
    <div>
      {% if %}
    </div>
    """


class BrokenAtRender(BaseComponent):
    template = """
    <div>
      {{ nothing.here }}
    </div>
    """


class Email(BaseComponent):
    """A pydantic field that happens to be called ``template``."""

    template: str = "welcome"  # pyright: ignore[reportIncompatibleVariableOverride]


class WelcomeEmail(Email):
    pass


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def test_a_class_can_assign_its_template_without_an_annotation():
    assert "template" not in Chip.model_fields
    assert "<span" in Chip.template


def test_a_field_named_template_is_still_a_field():
    assert "template" in Email.model_fields
    assert Email().template == "welcome"
    assert Email(template="reset").template == "reset"
    assert WelcomeEmail().template == "welcome"


def test_declaring_a_field_named_template_warns_about_nothing():
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        class Receipt(BaseComponent):
            template: str  # pyright: ignore[reportIncompatibleVariableOverride]

    assert Receipt(template="x").template == "x"


def test_an_inline_template_resolves_to_the_module_that_defines_it():
    descriptor = Chip.__pjx_descriptor__
    assert descriptor.template_path == THIS_FILE
    assert descriptor.inline_class == "Chip"
    assert descriptor.provenance["template"] is Chip


def test_a_file_template_has_no_inline_class():
    class Plain(BaseComponent):
        pass

    assert Plain.__pjx_descriptor__.inline_class is None


def test_a_subclass_inherits_its_parents_inline_template():
    assert LoudChip.__pjx_descriptor__.template_path == THIS_FILE
    assert LoudChip.__pjx_descriptor__.inline_class == "Chip"


def test_a_subclass_can_replace_the_inline_template():
    assert QuietChip.__pjx_descriptor__.inline_class == "QuietChip"


def test_a_field_named_template_is_not_an_inline_template():
    descriptor = Email.__pjx_descriptor__
    assert descriptor.inline_class is None
    assert descriptor.template_path == THIS_FILE.parent / "email.pjx"


def test_the_loader_reports_the_python_file_as_the_templates_filename():
    source, filename, uptodate = AbsolutePathLoader().get_source(
        jinja2.Environment(), f"{THIS_FILE}::Chip"
    )
    assert '<span class="chip">' in source
    assert "class Chip" not in source
    assert filename == str(THIS_FILE)
    assert uptodate() is True


def test_the_loader_does_not_find_a_class_the_module_lacks():
    with pytest.raises(ValueError, match="Nope"):
        AbsolutePathLoader().get_source(jinja2.Environment(), f"{THIS_FILE}::Nope")


def test_the_loader_does_not_find_a_missing_module():
    with pytest.raises(jinja2.TemplateNotFound):
        AbsolutePathLoader().get_source(
            jinja2.Environment(), f"{THIS_FILE.parent / 'nope.py'}::Chip"
        )


def test_an_inline_template_renders():
    assert Chip(label="new").render() == '<span class="chip">new</span>'


def test_a_subclass_renders_its_parents_inline_template():
    assert LoudChip(label="hey").render() == '<span class="chip">hey</span>'


def test_a_subclass_renders_its_own_replacement():
    assert QuietChip(label="hey").render() == "<small>hey</small>"


def test_a_class_with_methods_and_validators_renders_from_its_inline_template():
    price = Price.free()
    assert price.amount == "0.00"
    assert price.render() == '<data value="0">EUR</data>'


def test_inline_components_are_registered_and_expand_as_tags():
    discovery.build_registry(None, [Chip, ChipRow])
    assert discovery.get_class("chip") is Chip
    assert ChipRow().render() == (
        '<div class="row"><span class="chip">one</span>'
        '<span class="chip">two</span></div>'
    )


def test_a_syntax_error_points_at_the_line_in_the_python_file():
    with pytest.raises(jinja2.TemplateSyntaxError) as caught:
        BrokenSyntax().render()
    assert caught.value.filename == str(THIS_FILE)
    assert caught.value.lineno == line_of("{% if %}")


def test_a_render_error_traceback_points_at_the_line_in_the_python_file():
    with pytest.raises(jinja2.UndefinedError) as caught:
        BrokenAtRender().render()
    frames = traceback.extract_tb(caught.tb)
    template_frame = next(f for f in frames if "template code" in f.name)
    assert template_frame.filename == str(THIS_FILE)
    assert template_frame.lineno == line_of("{{ nothing.here }}")
    assert template_frame.line == "{{ nothing.here }}"


def _import_file(path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Template resolution finds a class's file through sys.modules.
    monkeypatch.setitem(sys.modules, path.stem, module)
    spec.loader.exec_module(module)
    return module


def _touch_later(path: Path) -> None:
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 10))


def test_editing_the_template_on_disk_is_picked_up_without_reimporting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "from pyjinhx import BaseComponent\n\n\n"
        "class ReloadedNote(BaseComponent):\n"
        '    template = "<p>before</p>"\n'
    )
    path = tmp_path / "reloaded_note.py"
    path.write_text(source)
    note = _import_file(path, monkeypatch).ReloadedNote()
    assert note.render() == "<p>before</p>"

    path.write_text(source.replace("before", "after"))
    _touch_later(path)

    assert note.render() == "<p>after</p>"


SHOP = '''\
from pydantic import computed_field

from pyjinhx import BaseComponent, ReactiveComponent

STORE = {"remaining": 3}


class Counter(ReactiveComponent, react={"todos"}):
    remaining: int = 0

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=STORE["remaining"])

    @computed_field
    @property
    def noun(self) -> str:
        return "item" if self.remaining == 1 else "items"

    template = r"""
    <div class="counter">{{ remaining }} {{ noun }} left</div>
    """


class Pinned(BaseComponent):
    auto_id = False

    template = '<p id="{{ id }}">pinned</p>'


class Card(BaseComponent):
    template = "<div>inline</div>"


class FancyCard(Card):
    pass


class Email(BaseComponent):
    template: str = "welcome"
'''


@pytest.fixture
def shop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A module of several components, with a few sibling .pjx files."""
    (tmp_path / "card.pjx").write_text("<div>file</div>")
    (tmp_path / "fancy_card.pjx").write_text("<div>fancy file</div>")
    (tmp_path / "email.pjx").write_text("<p>{{ template }}</p>")
    path = tmp_path / "shop.py"
    path.write_text(SHOP)
    return _import_file(path, monkeypatch)


def test_a_reactive_component_renders_from_its_inline_template(shop):
    with request_scope():
        out = shop.Counter.load().render()
    assert '<div class="counter"' in out
    assert "3 items left</div>" in out


def test_a_class_level_auto_id_still_requires_an_id(shop):
    assert shop.Pinned(id="p1").render() == '<p id="p1">pinned</p>'
    with pytest.raises(ValueError, match="id is required"):
        shop.Pinned()


def test_an_inline_template_wins_over_an_adjacent_file(shop):
    assert shop.Card().render() == "<div>inline</div>"


def test_a_subclass_file_overrides_a_parents_inline_template(shop):
    assert shop.FancyCard.__pjx_descriptor__.inline_class is None
    assert shop.FancyCard().render() == "<div>fancy file</div>"


def test_a_field_named_template_renders_from_its_file(shop):
    assert shop.Email(template="reset").render() == "<p>reset</p>"


def test_the_render_cache_key_follows_the_modules_mtime(shop):
    card = shop.Card(id="c")
    before = render_cache_key(card)
    _touch_later(Path(shop.__file__))
    assert render_cache_key(card) != before


STYLED = '''\
from pyjinhx import BaseComponent


class Tag(BaseComponent):
    template = r"""
    <span class="tag">tag</span>
    {#css
    .tag { color: red; }
    #}
    """


class Pill(BaseComponent):
    template = r"""
    <span class="pill">pill</span>
    {#css
    .pill { color: blue; }
    #}
    {#js
    console.log("pill");
    #}
    """


class Shelf(BaseComponent):
    template = "<div><Tag/><Tag/><Pill/></div>"
'''


@pytest.fixture
def styled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A module of components carrying their own css and js blocks."""
    path = tmp_path / "styled.py"
    path.write_text(STYLED)
    return _import_file(path, monkeypatch)


def _collecting_session() -> RenderSession:
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    return session


def test_an_inline_css_block_becomes_the_classs_asset(styled):
    path = Path(styled.__file__)
    (css,) = styled.Tag.__pjx_descriptor__.css_paths
    assert isinstance(css, InlineAsset)
    assert str(css) == f"{path}::Tag#css"
    assert css.read_text() == ".tag { color: red; }"
    assert styled.Tag.__pjx_descriptor__.js_paths == ()


def test_two_components_in_one_module_keep_their_own_blocks(styled):
    (tag_css,) = styled.Tag.__pjx_descriptor__.css_paths
    (pill_css,) = styled.Pill.__pjx_descriptor__.css_paths
    (pill_js,) = styled.Pill.__pjx_descriptor__.js_paths
    assert tag_css != pill_css
    assert pill_css.read_text() == ".pill { color: blue; }"
    assert pill_js.read_text() == 'console.log("pill");'


def test_rendering_inlines_each_block_once(styled):
    discovery.build_registry(None, [styled.Tag, styled.Pill, styled.Shelf])
    out = render(styled.Shelf(), _collecting_session())
    (tag_css,) = styled.Tag.__pjx_descriptor__.css_paths
    token = asset_token(tag_css)
    assert f'<style data-pjx-asset="{token}">.tag {{ color: red; }}</style>' in out
    assert out.count(".tag { color: red; }") == 1
    assert out.count('console.log("pill")') == 1
    assert "{#" not in out


def test_a_duplicate_block_is_reported_at_its_line_in_the_python_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "twice.py"
    path.write_text(
        "from pyjinhx import BaseComponent\n"
        "\n"
        "\n"
        "class Twice(BaseComponent):\n"
        '    template = """\n'
        "    <div></div>\n"
        "    {#js a(); #}\n"
        "    {#js b(); #}\n"
        '    """\n'
    )
    with pytest.raises(jinja2.TemplateSyntaxError) as caught:
        _import_file(path, monkeypatch)
    assert caught.value.filename == str(path)
    assert caught.value.lineno == 8


def test_a_sibling_file_and_an_inline_block_ship_sibling_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "tag.css").write_text(".sibling {}")
    path = tmp_path / "styled.py"
    path.write_text(STYLED)
    tag = _import_file(path, monkeypatch).Tag
    sibling, block = tag.__pjx_descriptor__.css_paths
    assert sibling == tmp_path / "tag.css"
    assert str(block) == f"{path}::Tag#css"


def test_editing_a_block_on_disk_changes_what_the_asset_reads(styled):
    path = Path(styled.__file__)
    (css,) = styled.Tag.__pjx_descriptor__.css_paths
    path.write_text(STYLED.replace("color: red", "color: green"))
    assert css.read_text() == ".tag { color: green; }"


def test_an_inline_asset_survives_pickling(styled):
    (css,) = styled.Pill.__pjx_descriptor__.css_paths
    restored = pickle.loads(pickle.dumps(css))
    assert isinstance(restored, InlineAsset)
    assert restored == css
    assert restored.read_text() == ".pill { color: blue; }"


def test_an_inline_template_with_a_def_header_is_reported_as_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    path = tmp_path / "headed.py"
    path.write_text(
        "from pyjinhx import BaseComponent\n\n\n"
        "class Headed(BaseComponent):\n"
        "    title: str\n\n"
        '    template = """\n'
        "    {#def title: str #}\n"
        "    <h1>{{ title }}</h1>\n"
        '    """\n'
    )
    headed = _import_file(path, monkeypatch).Headed
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        headed(title="a").render()
        headed(title="b").render()
    assert [r.getMessage() for r in caplog.records].count(
        "<Headed>: a {#def#} header is present but a Python class is registered "
        "— the header is ignored. Remove the header (or the class)."
    ) == 1


def _headed_module(tmp_path: Path, template_lines: list[str]) -> Path:
    path = tmp_path / "headed.py"
    path.write_text(
        "from pyjinhx import BaseComponent\n\n\n"
        "class Headed(BaseComponent):\n"
        "    title: str = 'x'\n\n"
        '    template = """\n'
        + "".join(f"    {line}\n" for line in template_lines)
        + '    """\n'
    )
    return path


@pytest.mark.parametrize(
    "template_lines",
    [
        ["{# def title: str #}", "<h1>{{ title }}</h1>"],
        ["<h1>{{ title }}</h1>", "{#def title: str #}"],
    ],
    ids=["legacy-spaced-first", "header-after-markup"],
)
def test_an_inline_header_is_seen_wherever_a_pjx_header_would_be(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template_lines: list[str]
):
    path = _headed_module(tmp_path, template_lines)
    headed = _import_file(path, monkeypatch).Headed
    assert headed.__pjx_descriptor__.has_stale_def_header is True


def test_a_stray_comment_close_in_an_inline_block_is_reported_in_the_python_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = _headed_module(tmp_path, ["<div></div>", "{#css a { b: '#}' } #}"])
    with pytest.raises(jinja2.TemplateSyntaxError) as caught:
        _import_file(path, monkeypatch)
    assert caught.value.filename == str(path)
    assert caught.value.lineno == 9


def test_an_inline_class_claims_its_tag_over_a_namesake_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from pyjinhx.classless import component_for_tag

    (tmp_path / "headed.pjx").write_text("{#def title: str #}<p>file</p>")
    headed = _import_file(_headed_module(tmp_path, ["<h1>inline</h1>"]), monkeypatch)
    discovery.build_registry(tmp_path, [headed.Headed])

    assert discovery.get_orphan_templates("headed") == ()
    assert component_for_tag("Headed") is headed.Headed
