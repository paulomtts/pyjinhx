"""Tests for render_context module."""

from pathlib import Path
from typing import ClassVar

import pytest
from jinja2 import Environment
from pydantic import BaseModel, ValidationError

from pyjinhx2.component import BaseComponent, Slot, _resolve_slot_fields
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.markers import ComponentNode
from pyjinhx2.render_context import build_context


def test_component_node_marker_identity():
    """ComponentNode is not a string so Jinja filters fail fast."""

    class DummyComponent(BaseComponent):
        pass

    comp = DummyComponent()
    node = ComponentNode(
        comp,
        owner_name="DummyComponent",
        owner_template=Path("dummy.pjx"),
        field_name="content",
    )

    # Verify it's not a string
    assert not isinstance(node, str)
    # Verify it holds the component reference
    assert node.component is comp
    # Verify len() fails with the targeted opacity error (as Jinja would try)
    with pytest.raises(TypeError, match=r"slot 'content' holds a rendered component"):
        len(node)  # type: ignore[arg-type]


def test_basic_field_passthrough():
    """Non-slot fields pass to Jinja as-is."""

    class Card(BaseComponent):
        title: str
        count: int

    card = Card(title="Hello", count=5)
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=frozenset(),
        children_field=None,
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
        children_field=None,
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
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    context = build_context(card, descriptor)

    # String-valued slot should pass through as a string
    assert isinstance(context["html_content"], str)
    assert context["html_content"] == "<p>Safe markup</p>"


def test_auto_slot_component_valued_field():
    """A bare component-typed field is a slot without any annotation, so its
    value is wrapped in ComponentNode like an explicit Slot would be."""

    class Child(BaseComponent):
        name: str

    class Parent(BaseComponent):
        # No Slot annotation: the component-typed annotation is enough.
        child: Child

    child = Child(name="x")
    parent = Parent(child=child)
    descriptor = ClassDescriptor(
        template_path=Path("parent.pjx"),
        slot_fields=_resolve_slot_fields(Parent),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    assert descriptor.slot_fields == frozenset({"child"})

    context = build_context(parent, descriptor)

    assert isinstance(context["child"], ComponentNode)
    assert context["child"].component is child


def test_component_collection_slot_entries_are_not_wrapped_yet():
    """Auto-detection makes list/dict component fields slots at registration
    time; per-entry ComponentNode wrapping in build_context is a separate,
    unclosed gap (list/dict slot semantics, #371) and is not in #418's scope."""

    class Badge(BaseComponent):
        label: str = ""

    class Card(BaseComponent):
        badges: list[Badge] = []

    card = Card(badges=[Badge(label="a")])
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=_resolve_slot_fields(Card),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )

    assert descriptor.slot_fields == frozenset({"badges"})

    context = build_context(card, descriptor)

    # Documents current behaviour, not desired behaviour: model_dump() already
    # flattened the entries and build_context does not iterate collections.
    assert not isinstance(context["badges"], ComponentNode)


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
        children_field=None,
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
        children_field=None,
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
        children_field=None,
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
        children_field=None,
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
        children_field=None,
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


@pytest.mark.parametrize(
    "source",
    [
        "{{ content|length }}",
        "{{ content[0:3] }}",
        "{{ 'x' in content }}",
        "{{ content == 'x' }}",
    ],
)
def test_forbidden_operations_fail_through_jinja(source):
    """Every forbidden op raises the opacity TypeError via a real render."""

    class Inner(BaseComponent):
        pass

    class Card(BaseComponent):
        content: Slot

    card = Card(content=Inner())
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=frozenset(["content"]),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )
    context = build_context(card, descriptor)

    env = Environment(autoescape=True)

    with pytest.raises(TypeError) as excinfo:
        template = env.from_string(source)
        template.render(context)

    assert "Card (template: card.pjx): slot 'content'" in str(excinfo.value)


@pytest.mark.parametrize(
    "source", ["{{ content|striptags }}", "{{ content|trim }}", "{{ content|upper }}"]
)
def test_str_routed_filters_do_not_raise(source):
    """`|striptags`/`|trim`/`|upper` call str() first, so they render __str__'s
    output instead of raising. This is a documented gap (see PR description),
    not a bug: the ADR's opacity guarantee is delivered by raising from the
    dunder each operation actually reaches, and these three filters never
    reach one. Locking this in as a regression test rather than a TODO.
    """

    class Inner(BaseComponent):
        pass

    class Card(BaseComponent):
        content: Slot

    card = Card(content=Inner())
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=frozenset(["content"]),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )
    context = build_context(card, descriptor)

    env = Environment(autoescape=True)
    # Must not raise; exact output is __str__'s business, not this test's.
    env.from_string(source).render(context)


def test_string_slot_is_unaffected_by_opacity():
    """A plain-str Slot keeps working with string filters and slicing."""

    class Note(BaseComponent):
        text_field: Slot

    note = Note(text_field="hello world")
    descriptor = ClassDescriptor(
        template_path=Path("note.pjx"),
        slot_fields=frozenset(["text_field"]),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )
    context = build_context(note, descriptor)

    env = Environment(autoescape=True)

    assert env.from_string("{{ text_field|length }}").render(context) == "11"
    assert env.from_string("{{ text_field[0:5] }}").render(context) == "hello"


def test_interpolation_and_truthiness_still_work():
    """`{{ content }}` and `{% if content %}` remain the two allowed forms."""

    class Inner(BaseComponent):
        pass

    class Card(BaseComponent):
        content: Slot

    card = Card(content=Inner())
    descriptor = ClassDescriptor(
        template_path=Path("card.pjx"),
        slot_fields=frozenset(["content"]),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )
    context = build_context(card, descriptor)

    env = Environment(autoescape=True)

    assert env.from_string("{% if content %}yes{% endif %}").render(context) == "yes"
    # Interpolation must not raise; its exact output is L1 child-expansion work.
    env.from_string("{{ content }}").render(context)


def test_strict_component_no_extra_keys():
    """Strict components reject extra keys at construction (Pydantic level)."""

    class StrictCard(BaseComponent):
        model_config: ClassVar = {"extra": "forbid"}  # type: ignore[misc]
        title: str

    # Construction with extra key should fail at Pydantic level
    with pytest.raises(ValidationError):
        StrictCard(title="x", unknown="y")  # type: ignore[call-arg]


def test_context_builder_does_not_catch_pydantic_errors():
    """build_context passes Pydantic errors through unchanged.

    If model_dump() would hit an error (circular ref, etc.),
    build_context doesn't catch it. This is caller's responsibility.
    """
    # This is a documentation test. Pydantic's construction-time validation
    # prevents most bad types from reaching model_dump(). If caller constructs
    # valid component and descriptor, build_context will succeed.


def test_component_node_is_always_truthy():
    """A wrapped component is truthy without any render being forced."""

    class Dummy(BaseComponent):
        pass

    node = ComponentNode(Dummy())
    assert bool(node) is True


def test_component_node_truthiness_does_not_use_len():
    """__bool__ must answer directly; len() stays broken (ADR 0003)."""

    class Dummy(BaseComponent):
        pass

    node = ComponentNode(Dummy())
    if node:
        pass
    with pytest.raises(TypeError):
        len(node)  # type: ignore[arg-type]
    assert not hasattr(node, "__str__") or type(node).__str__ is object.__str__
    assert not hasattr(node, "__html__")


def test_finalize_passes_non_component_values_through_unchanged():
    from pyjinhx2.markers import collect_slot_tokens, finalize_slot_node

    with collect_slot_tokens():
        assert finalize_slot_node("plain") == "plain"
        assert finalize_slot_node(7) == 7
        assert finalize_slot_node(None) is None


def test_finalize_registers_a_component_node_under_a_unique_token():
    from pyjinhx2.markers import SLOT_TOKEN_RE, collect_slot_tokens, finalize_slot_node

    class Dummy(BaseComponent):
        pass

    first, second = Dummy(), Dummy()
    with collect_slot_tokens() as table:
        token_a = finalize_slot_node(ComponentNode(first))
        token_b = finalize_slot_node(ComponentNode(second))

        assert isinstance(token_a, str)
        assert SLOT_TOKEN_RE.fullmatch(token_a)
        assert token_a != token_b
        assert table[token_a] is first  # type: ignore[index]
        assert table[token_b] is second  # type: ignore[index]


def test_token_tables_do_not_leak_between_scopes():
    from pyjinhx2.markers import collect_slot_tokens, finalize_slot_node

    class Dummy(BaseComponent):
        pass

    with collect_slot_tokens() as outer:
        outer_token = finalize_slot_node(ComponentNode(Dummy()))
        with collect_slot_tokens() as inner:
            inner_token = finalize_slot_node(ComponentNode(Dummy()))
            assert outer_token not in inner
        assert inner_token not in outer
        assert outer_token in outer


def test_token_is_autoescape_inert():
    """The token must survive Markup escaping byte-for-byte."""
    from markupsafe import escape

    from pyjinhx2.markers import collect_slot_tokens, finalize_slot_node

    class Dummy(BaseComponent):
        pass

    with collect_slot_tokens():
        token = finalize_slot_node(ComponentNode(Dummy()))
    assert str(escape(token)) == token
