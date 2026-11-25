"""Tests for components that carry their template inline, in this very file."""

import warnings
from pathlib import Path

import jinja2
import pytest

from pyjinhx import BaseComponent, discovery
from pyjinhx.session import AbsolutePathLoader

THIS_FILE = Path(__file__)


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
