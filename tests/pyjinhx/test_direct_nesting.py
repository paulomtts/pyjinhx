"""L1.3.4 — a component instance assigned directly to a slot field in Python
renders as an opaque child node (#370).

Confirmatory: no production code changes. The pipeline under test is
build_context() wrapping the field value in ComponentNode, the Jinja finalize
hook emitting a placeholder token, and _splice_slot_nodes() replacing that
token with the child's own render_level() result — the same path a tag-mounted
child takes, reached here from a plain constructor kwarg instead.
"""

from pathlib import Path
from typing import Annotated, Any

import pytest

from pyjinhx.component import BaseComponent, Children, PjxSlot, Slot
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.markers import ComponentNode
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.render_context import build_context
from pyjinhx.rendering import render, render_level
from pyjinhx.segments import RenderedLevel
from pyjinhx.session import RenderSession


def descriptor(template: str, slots: frozenset[str], children: str | None = None):
    """A ClassDescriptor pointing at a fixture template under tests/templates."""
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=slots,
        children_field=children,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={},
    )


def session() -> RenderSession:
    return RenderSession(template_dir="tests/templates")


class Leaf(BaseComponent):
    text: str = "x"


Leaf.__pjx_descriptor__ = descriptor("nest_leaf.html", frozenset())


class TestBareSlotField:
    def test_instance_assigned_in_python_renders_its_own_template(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        output = render(Card(content=Leaf(text="hi")), session())

        assert output == '<div class="card"><span class="leaf">hi</span></div>'

    def test_a_hand_built_reactive_instance_renders_its_own_field_unrefetched(self):
        # #727 non-goal: _splice_slot_nodes stays untouched, so a
        # ReactiveComponent built by hand and assigned straight to a slot
        # field must render as-is — the slot path never calls load() at all,
        # unlike a ChildRef-mounted reactive child.
        load_calls: list[str] = []

        class ReactiveLeaf(ReactiveComponent):
            text: str = "x"

            @classmethod
            def load(cls) -> "ReactiveLeaf":
                load_calls.append("called")
                return cls(text="from-load")

        ReactiveLeaf.__pjx_descriptor__ = descriptor("nest_leaf.html", frozenset())

        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        output = render(Card(content=ReactiveLeaf(text="hand-set")), session())

        assert output == '<div class="card"><span class="leaf">hand-set</span></div>'
        assert load_calls == []

    def test_child_enters_segments_as_a_whole_rendered_level(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        level = render_level(Card(content=Leaf(text="hi")), session())

        nested = [s for s in level.segments if isinstance(s, RenderedLevel)]
        assert len(nested) == 1
        assert "hi" not in "".join(s for s in level.segments if isinstance(s, str))


class TestSlotFieldOrigin:
    def test_children_flagged_field_under_a_non_content_name(self):
        class Wrap(BaseComponent):
            inner: Children = ""

        Wrap.__pjx_descriptor__ = descriptor(
            "nest_wrap.html", frozenset({"inner"}), "inner"
        )

        output = render(Wrap(inner=Leaf(text="a")), session())

        assert output == '<section class="wrap"><span class="leaf">a</span></section>'

    def test_bare_marker_on_an_arbitrarily_named_field(self):
        class Wrap(BaseComponent):
            inner: Annotated[str | BaseComponent, PjxSlot()] = ""

        Wrap.__pjx_descriptor__ = descriptor(
            "nest_wrap.html", frozenset({"inner"}), None
        )

        output = render(Wrap(inner=Leaf(text="b")), session())

        assert output == '<section class="wrap"><span class="leaf">b</span></section>'


class TestTruthiness:
    def test_if_branch_taken_when_a_component_is_assigned(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_if.html", frozenset({"content"}), "content"
        )

        output = render(Card(content=Leaf(text="c")), session())

        assert output == (
            '<div class="card"><b>filled</b><span class="leaf">c</span></div>'
        )

    def test_else_branch_taken_when_the_slot_is_left_at_its_default(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_if.html", frozenset({"content"}), "content"
        )

        assert render(Card(), session()) == '<div class="card"><i>empty</i></div>'


class TestNestedOfNested:
    def test_three_levels_compose_in_order(self):
        class Middle(BaseComponent):
            inner: Slot = ""

        Middle.__pjx_descriptor__ = descriptor(
            "nest_wrap.html", frozenset({"inner"}), "inner"
        )

        class Outer(BaseComponent):
            content: Slot = ""

        Outer.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        output = render(Outer(content=Middle(inner=Leaf(text="deep"))), session())

        assert output == (
            '<div class="card"><section class="wrap">'
            '<span class="leaf">deep</span></section></div>'
        )

    def test_each_level_parses_exactly_once(self, monkeypatch):
        class Middle(BaseComponent):
            inner: Slot = ""

        Middle.__pjx_descriptor__ = descriptor(
            "nest_wrap.html", frozenset({"inner"}), "inner"
        )

        class Outer(BaseComponent):
            content: Slot = ""

        Outer.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        import pyjinhx.rendering as render_module

        real_parser = render_module.VerbatimParser
        calls: list[int] = []

        def counting_parser(*args: object, **kwargs: object):
            calls.append(1)
            return real_parser(*args, **kwargs)

        monkeypatch.setattr(render_module, "VerbatimParser", counting_parser)

        render(Outer(content=Middle(inner=Leaf(text="deep"))), session())

        assert len(calls) == 3


class TestCycle:
    def test_assigning_an_instance_of_the_same_class_terminates_and_renders(self):
        # Reusing a class at a shallower and a deeper level of the same path is
        # not a cycle by itself — this path terminates at Leaf, so it must
        # render rather than raise (#645: same-class-anywhere was a false
        # positive; only a path that stops making progress is a cycle).
        class Recur(BaseComponent):
            content: Slot = ""

        Recur.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        assert render(Recur(content=Recur(content=Leaf(text="z"))), session()) == (
            '<div class="card"><div class="card">'
            '<span class="leaf">z</span></div></div>'
        )


class TestBoundaries:
    def test_a_component_on_a_non_slot_field_is_not_wrapped(self):
        class Card(BaseComponent):
            content: str = ""
            sidecar: Any = None

        Card.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        component = Card(content="plain", sidecar=Leaf(text="q"))
        context = build_context(component, Card.__pjx_descriptor__)

        # build_context() sources the context from component.model_dump(),
        # which recursively serializes nested BaseModel/BaseComponent values
        # into plain dicts — so a non-slot field's component value survives
        # as neither a ComponentNode nor the original instance, only a dict.
        assert not isinstance(context["sidecar"], ComponentNode)
        assert isinstance(context["sidecar"], dict)
        assert not isinstance(context["sidecar"], Leaf)

    def test_a_string_valued_slot_stays_a_plain_string(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"}), "content"
        )

        context = build_context(Card(content="<b>raw</b>"), Card.__pjx_descriptor__)

        assert not isinstance(context["content"], ComponentNode)
        assert context["content"] == "<b>raw</b>"

    def test_a_slot_interpolated_into_an_attribute_still_raises(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_attr.html", frozenset({"content"}), "content"
        )

        with pytest.raises(ValueError, match="inside a tag"):
            render(Card(content=Leaf(text="x")), session())
