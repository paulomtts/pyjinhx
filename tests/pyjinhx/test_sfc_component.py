"""Tests for components that carry their template inline, in this very file."""

import importlib.util
import os
import sys
import traceback
from pathlib import Path

import jinja2
import pytest
from pydantic import field_validator

from pyjinhx import BaseComponent, discovery
from pyjinhx.session import AbsolutePathLoader

THIS_FILE = Path(__file__)


def line_of(text: str) -> int:
    """The 1-based line of this file where ``text`` first appears."""
    lines = THIS_FILE.read_text(encoding="utf-8").splitlines()
    return next(number for number, line in enumerate(lines, 1) if text in line)


def _shout(text: str) -> str:
    return text.upper()


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
        return cls(cents=0)

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


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def test_an_inline_template_resolves_to_the_module_that_defines_it():
    descriptor = Chip.__pjx_descriptor__
    assert descriptor.template_path == THIS_FILE
    assert descriptor.inline_class == "Chip"
    assert descriptor.provenance["template"] is Chip


def test_a_file_template_has_no_inline_class():
    class Plain(BaseComponent):
        pass

    assert Plain.__pjx_descriptor__.inline_class is None


def test_an_inline_template_renders():
    assert Chip(label="new").render() == '<span class="chip">new</span>'


def test_a_subclass_inherits_its_parents_inline_template():
    assert LoudChip.__pjx_descriptor__.inline_class == "Chip"
    assert LoudChip(label="hey").render() == '<span class="chip">hey</span>'


def test_a_subclass_can_replace_the_inline_template():
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
    spec = importlib.util.spec_from_file_location("reloaded_note", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Template resolution finds a class's file through sys.modules.
    monkeypatch.setitem(sys.modules, "reloaded_note", module)
    spec.loader.exec_module(module)
    note = module.ReloadedNote()
    assert note.render() == "<p>before</p>"

    path.write_text(source.replace("before", "after"))
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 10))

    assert note.render() == "<p>after</p>"
