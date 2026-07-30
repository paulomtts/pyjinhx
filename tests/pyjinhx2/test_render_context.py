"""Tests for render_context module."""
import pytest
from pathlib import Path
from pydantic import BaseModel

from pyjinhx2.component import BaseComponent, Slot
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.markers import ComponentNode
from pyjinhx2.render_context import build_context


def test_component_node_marker_identity():
    """ComponentNode is not a string so Jinja filters fail fast."""

    class DummyComponent(BaseComponent):
        pass

    comp = DummyComponent()
    node = ComponentNode(comp)

    # Verify it's not a string
    assert not isinstance(node, str)
    # Verify it holds the component reference
    assert node.component is comp
    # Verify len() fails (as Jinja would try)
    with pytest.raises(TypeError):
        len(node)


def test_basic_field_passthrough():
    """Non-slot fields pass to Jinja as-is."""

    class Card(BaseComponent):
        title: str
        count: int

    card = Card(title="Hello", count=5)
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(card, descriptor)

    assert context["title"] == "Hello"
    assert context["count"] == 5
    assert "id" in context  # auto-id should be present


def test_slot_field_wrapping_component_valued():
    """Component-valued Slot fields are wrapped with ComponentNode."""

    class InnerComponent(BaseComponent):
        name: str = "inner"

    class CardWithContent(BaseComponent):
        title: str
        content: Slot

    inner = InnerComponent()
    card = CardWithContent(title="x", content=inner)
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=frozenset(["content"]),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(card, descriptor)

    # content should be wrapped, not a string
    assert isinstance(context["content"], ComponentNode)
    assert context["content"].component is inner
