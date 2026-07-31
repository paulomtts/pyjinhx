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
