"""L1.3.7 — the ADR 0003 slot semantics matrix.

Cross-feature combinations of the behaviors #367-#372 each shipped in
isolation: truthiness together with interpolation, every forbidden operation
against one component slot, children inference alongside a directly nested
slot, collections combined with interpolation and `.props`, the `.props`
escape hatch's boundaries, and per-render token isolation.

Test-only: everything here exercises code that already exists. Where current
behavior does not match the ADR (the stringifying filters), the test pins what
happens today and says so.
"""

from pathlib import Path

import pytest

from pyjinhx2.component import BaseComponent, Slot
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.markers import ComponentNode, collect_slot_tokens
from pyjinhx2.render import render, render_level
from pyjinhx2.render_context import build_context
from pyjinhx2.session import RenderSession


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


def render_expr(expr: str, component: BaseComponent) -> str:
    """Render one Jinja expression against a component's real slot context.

    Compiled through the session's own environment, so the finalize hook and
    autoescape are exactly the ones the pipeline uses; the op matrix needs one
    line of template per operator, not one fixture file per operator.
    """
    context = build_context(component, type(component).__pjx_descriptor__)
    template = session().jinja_env.from_string(expr)
    with collect_slot_tokens():
        return template.render(context)


class TestHarness:
    def test_render_expr_sees_the_wrapped_slot(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("nest_content.html", frozenset({"content"}))

        assert render_expr("{% if content %}yes{% endif %}", Card(content=Leaf())) == "yes"


class TestTruthinessWithInterpolation:
    def card(self, template: str, slots: frozenset[str]):
        class Card(BaseComponent):
            content: Slot = ""
            note: Slot = ""

        Card.__pjx_descriptor__ = descriptor(template, slots)
        return Card

    def test_guarded_interpolation_renders_the_child_exactly_once(self):
        Card = self.card("nest_if.html", frozenset({"content"}))

        output = render(Card(content=Leaf(text="c")), session())

        assert output == (
            '<div class="card"><b>filled</b><span class="leaf">c</span></div>'
        )
        assert output.count('<span class="leaf">') == 1

    def test_the_guarded_branch_produces_one_nested_level(self):
        # A second render of the same child would show up as a second
        # RenderedLevel; the count is the double-render check.
        from pyjinhx2.segments import RenderedLevel

        Card = self.card("nest_if.html", frozenset({"content"}))

        level = render_level(Card(content=Leaf(text="c")), session())

        assert len([s for s in level.segments if isinstance(s, RenderedLevel)]) == 1

    def test_an_empty_slot_takes_the_else_branch_without_interpolating(self):
        Card = self.card("nest_if.html", frozenset({"content"}))

        output = render(Card(content=""), session())

        assert output == '<div class="card"><i>empty</i></div>'
        assert "pjx-slot-" not in output

    def test_a_string_slot_beside_a_component_slot_stays_raw_html(self):
        # Production gap, not a fixture bug: ADR 0003 constraint 2 says
        # plain-string Slot fields stay raw-HTML-capable, but with
        # autoescape ON (shipped after #367-#372) a bare string slot value
        # is escaped like any other Jinja variable — nothing in the render
        # pipeline currently marks Slot-typed strings as Markup. Pinned as
        # observed; flagged for follow-up rather than patched here.
        Card = self.card("slot_mixed_kinds.html", frozenset({"content", "note"}))

        output = render(
            Card(content=Leaf(text="c"), note="<em>raw</em>"), session()
        )

        assert output == (
            '<div class="card"><span class="leaf">c</span>&lt;em&gt;raw&lt;/em&gt;</div>'
        )

    def test_a_string_slot_is_not_wrapped_in_a_component_node(self):
        Card = self.card("slot_mixed_kinds.html", frozenset({"content", "note"}))

        context = build_context(
            Card(content=Leaf(text="c"), note="<em>raw</em>"),
            Card.__pjx_descriptor__,
        )

        assert type(context["content"]) is ComponentNode
        assert context["note"] == "<em>raw</em>"
        assert not isinstance(context["note"], ComponentNode)

    def test_string_slot_operations_are_not_forbidden(self):
        # Constraint 2: this ADR does not touch string-valued slots, so the
        # ops that are errors on a component slot stay legal here.
        Card = self.card("slot_mixed_kinds.html", frozenset({"content", "note"}))
        card = Card(content=Leaf(text="c"), note="<em>raw</em>")

        assert render_expr("{{ note|length }}", card) == "12"
        assert render_expr("{{ 'em' in note }}", card) == "True"
