"""Tests for components that carry their template inline, in this very file."""

import importlib.util
import os
import sys
import traceback
import warnings
from pathlib import Path

import jinja2
import pytest
from pydantic import field_validator

from pyjinhx import BaseComponent, discovery
from pyjinhx.session import AbsolutePathLoader

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
