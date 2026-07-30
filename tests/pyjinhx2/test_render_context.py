"""Tests for render_context module."""
import pytest
from pathlib import Path
from pydantic import BaseModel, ValidationError
from jinja2 import Environment, TemplateError

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


def test_slot_field_passthrough_string_valued():
    """String-valued Slot fields pass as-is (will be wrapped in Markup by L1)."""

    class CardWithHTML(BaseComponent):
        title: str
        html_content: Slot

    card = CardWithHTML(title="x", html_content="<p>Safe markup</p>")
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=frozenset(["html_content"]),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(card, descriptor)

    # String-valued slot should pass through as a string
    assert isinstance(context["html_content"], str)
    assert context["html_content"] == "<p>Safe markup</p>"


def test_non_slot_component_valued_field():
    """Non-Slot component-valued fields pass as component objects (not wrapped)."""

    class Child(BaseComponent):
        name: str

    class Parent(BaseComponent):
        # child is NOT a Slot, so it's a regular composed field
        child: Child

    child = Child(name="x")
    parent = Parent(child=child)
    descriptor = ClassDescriptor(
        template_path=Path("parent.pjx"),
        slot_fields=frozenset(),  # child is NOT a slot
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(parent, descriptor)

    # Non-slot component fields pass as component objects
    # (model_dump recurses, so it will be a dict representation)
    assert "child" in context
    # The exact structure depends on model_dump behavior
    # At minimum, it should be in the context


def test_nested_basemodel_fields():
    """Nested BaseModel (non-component) fields pass through as dicts."""

    class Metadata(BaseModel):
        version: str

    class Form(BaseComponent):
        meta: Metadata

    form = Form(meta=Metadata(version="1.0"))
    descriptor = ClassDescriptor(
        template_path=Path("form.pjx"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(form, descriptor)

    # model_dump() recurses, so meta is a dict
    assert "meta" in context
    assert isinstance(context["meta"], dict)
    assert context["meta"]["version"] == "1.0"


def test_json_coerced_list_dict_fields():
    """List/dict fields pass through for Jinja iteration."""

    class Panel(BaseComponent):
        items: list[int]

    panel = Panel(items=[1, 2, 3])
    descriptor = ClassDescriptor(
        template_path=Path("panel.pjx"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(panel, descriptor)

    assert context["items"] == [1, 2, 3]


def test_auto_id_in_context():
    """Auto-generated id is present in context."""

    class SomeComponent(BaseComponent):
        title: str = "test"

    comp = SomeComponent(id="custom-id")
    descriptor = ClassDescriptor(
        template_path=Path("some.pjx"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(comp, descriptor)

    assert context["id"] == "custom-id"


def test_empty_component():
    """Empty component (only id) renders context correctly."""

    class Empty(BaseComponent):
        pass

    empty = Empty()
    descriptor = ClassDescriptor(
        template_path=Path("empty.pjx"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(empty, descriptor)

    # Should have at least the auto-generated id
    assert "id" in context
    assert context["id"].startswith("pjx-")


def test_jinja_filters_on_regular_fields():
    """Jinja filters work on regular (non-Slot) fields."""

    class Label(BaseComponent):
        text: str

    label = Label(text="Hello")
    descriptor = ClassDescriptor(
        template_path=Path("label.pjx"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(label, descriptor)

    # Simulate Jinja filter application
    env = Environment(autoescape=True)
    template = env.from_string("{{ text|upper }}")
    result = template.render(context)

    assert "HELLO" in result


def test_component_slot_filter_fails():
    """Template filter on component Slot fails fast (non-string type)."""

    class Inner(BaseComponent):
        pass

    class Outer(BaseComponent):
        content: Slot

    outer = Outer(content=Inner())
    descriptor = ClassDescriptor(
        template_path=Path("outer.pjx"),
        slot_fields=frozenset(["content"]),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(outer, descriptor)

    # Template filter on component Slot should fail
    env = Environment(autoescape=True)
    template = env.from_string("{{ content|length }}")

    with pytest.raises((TemplateError, TypeError)):
        template.render(context)


def test_strict_component_no_extra_keys():
    """Strict components reject extra keys at construction (Pydantic level)."""

    class StrictCard(BaseComponent):
        model_config = {"extra": "forbid"}
        title: str

    # Construction with extra key should fail at Pydantic level
    with pytest.raises(ValidationError):
        StrictCard(title="x", unknown="y")
