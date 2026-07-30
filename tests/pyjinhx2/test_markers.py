"""Tests for the opaque ComponentNode marker and its forbidden-operation errors."""

from pathlib import Path

import pytest

from pyjinhx2.component import BaseComponent
from pyjinhx2.markers import ComponentNode


class Inner(BaseComponent):
    """Child component held inside a slot."""


def make_node(field_name: str = "content") -> ComponentNode:
    """A ComponentNode as build_context would construct it for Card.content."""
    return ComponentNode(
        Inner(),
        owner_name="Card",
        owner_template=Path("card.pjx"),
        field_name=field_name,
    )


def test_component_node_records_owner_identity():
    """ComponentNode remembers the parent class, template and slot name."""
    node = make_node()

    assert node.owner_name == "Card"
    assert node.owner_template == Path("card.pjx")
    assert node.field_name == "content"


EXPECTED_LENGTH_MESSAGE = (
    "Card (template: card.pjx): slot 'content' holds a rendered component, so "
    "`|length` is not supported on it. Component slots are opaque outside "
    "`{% if %}` and `{{ }}`: use `{% if content %}` to test for presence, or "
    "`{{ content }}` to render it directly. String filters, slicing, "
    "membership tests, and comparisons are not available on component slots."
)


def test_len_raises_with_exact_message():
    """len() on a component slot names the class, template, slot and fix."""
    node = make_node()

    with pytest.raises(TypeError) as excinfo:
        len(node)

    assert str(excinfo.value) == EXPECTED_LENGTH_MESSAGE


def test_message_names_the_actual_field():
    """The message interpolates the real slot name, not a placeholder."""
    node = make_node(field_name="footer")

    with pytest.raises(TypeError) as excinfo:
        len(node)

    assert "slot 'footer'" in str(excinfo.value)
    assert "{% if footer %}" in str(excinfo.value)
    assert "{{ footer }}" in str(excinfo.value)


def test_message_survives_unresolved_template():
    """An unknown template path degrades to a placeholder, not a crash."""
    node = ComponentNode(
        Inner(), owner_name="Card", owner_template=None, field_name="content"
    )

    with pytest.raises(TypeError) as excinfo:
        len(node)

    assert "Card (template: <unresolved>): slot 'content'" in str(excinfo.value)
