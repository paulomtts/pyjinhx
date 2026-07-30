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
