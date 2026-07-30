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


def test_indexing_raises():
    """Subscripting a component slot is forbidden."""
    node = make_node()

    with pytest.raises(TypeError, match=r"`\[0\]` is not supported"):
        node[0]


def test_slicing_raises():
    """Slicing a component slot reports the slice syntax that was written."""
    node = make_node()

    with pytest.raises(TypeError, match=r"`\[0:3\]` is not supported"):
        node[0:3]


def test_membership_raises():
    """`in` against a component slot is forbidden."""
    node = make_node()

    with pytest.raises(TypeError, match=r"`in` is not supported"):
        assert "x" in node


def test_iteration_raises():
    """Iterating a component slot is forbidden."""
    node = make_node()

    with pytest.raises(TypeError, match=r"`for` is not supported"):
        list(node)


def test_equality_raises():
    """`==` against a component slot is forbidden, whatever the other side."""
    node = make_node()

    with pytest.raises(TypeError, match=r"`==` is not supported"):
        _ = node == "x"


def test_inequality_raises():
    """`!=` is forbidden too - Python routes it through __ne__, not __eq__."""
    node = make_node()

    with pytest.raises(TypeError, match=r"`!=` is not supported"):
        _ = node != "x"


@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("<", lambda node: node < "x"),
        ("<=", lambda node: node <= "x"),
        (">", lambda node: node > "x"),
        (">=", lambda node: node >= "x"),
    ],
)
def test_ordering_comparisons_raise(operation, call):
    """Ordering comparisons name the exact operator that was written."""
    node = make_node()

    with pytest.raises(TypeError) as excinfo:
        call(node)

    assert f"`{operation}` is not supported" in str(excinfo.value)


def test_identity_still_works():
    """`is` bypasses __eq__, so internal identity checks stay usable."""
    node = make_node()
    other = make_node()

    assert node is not other


def test_node_is_truthy():
    """A slot holding a component tests true under `{% if %}`."""
    assert bool(make_node()) is True


def test_str_renders_placeholder_not_object_repr():
    """str() must not fall through to object's default repr-ish output."""
    text = str(make_node())

    assert "<pyjinhx2.markers.ComponentNode object at" not in text
