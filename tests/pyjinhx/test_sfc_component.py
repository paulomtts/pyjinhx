"""Tests for components that carry their template inline, in this very file."""

import warnings
from pathlib import Path

import pytest

from pyjinhx import BaseComponent, discovery

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
