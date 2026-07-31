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


def opaque_card() -> BaseComponent:
    """A Card whose `content` slot holds a component, for the op matrix."""

    class Card(BaseComponent):
        content: Slot = ""

    Card.__pjx_descriptor__ = descriptor("nest_content.html", frozenset({"content"}))
    return Card(content=Leaf(text="c"))


class TestForbiddenOperations:
    @pytest.mark.parametrize(
        ("expr", "syntax"),
        [
            ("{{ content|length }}", "|length"),
            ("{{ 'x' in content }}", "in"),
            ("{% for x in content %}{{ x }}{% endfor %}", "for"),
            ("{{ content == 1 }}", "=="),
            ("{{ content != 1 }}", "!="),
            ("{{ content < 1 }}", "<"),
            ("{{ content <= 1 }}", "<="),
            ("{{ content > 1 }}", ">"),
            ("{{ content >= 1 }}", ">="),
        ],
    )
    def test_each_forbidden_operation_raises_the_opacity_error(self, expr, syntax):
        with pytest.raises(TypeError) as excinfo:
            render_expr(expr, opaque_card())

        message = str(excinfo.value)
        assert "slot 'content' holds a rendered component" in message
        assert f"`{syntax}`" in message

    def test_the_error_names_the_owner_component_and_template(self):
        with pytest.raises(TypeError) as excinfo:
            render_expr("{{ content|length }}", opaque_card())

        message = str(excinfo.value)
        assert message.startswith("Card (template: nest_content.html):")

    def test_the_error_points_at_the_two_supported_forms(self):
        with pytest.raises(TypeError) as excinfo:
            render_expr("{{ content|length }}", opaque_card())

        message = str(excinfo.value)
        assert "{% if content %}" in message
        assert "{{ content }}" in message

    def test_slicing_reports_the_slice_syntax(self):
        with pytest.raises(TypeError, match=r"`\[1:2\]`"):
            render_expr("{{ content[1:2] }}", opaque_card())

    def test_integer_indexing_raises_when_called_directly(self):
        # ComponentNode.__getitem__ itself raises the opaque error...
        node = ComponentNode(Leaf(text="c"), field_name="content")

        with pytest.raises(TypeError, match=r"`\[0\]`"):
            node[0]

    def test_integer_indexing_through_jinja_subscript_syntax_is_a_gap(self):
        # ...but `content[0]` inside a template does not raise it. Jinja's
        # `Environment.getitem` (dynamic subscript path) catches TypeError
        # and LookupError from `obj[argument]` and falls back to Undefined
        # instead of re-raising, so the opaque error never surfaces here —
        # unlike the slice case above, which the compiler routes through a
        # direct `__getitem__` call. Production gap: pin current behavior,
        # do not patch (test-only subtask, see ADR 0003 gap notes).
        assert render_expr("{{ content[0] }}", opaque_card()) == ""


class TestHashingSurvivesForbiddenEquality:
    def test_a_node_is_usable_as_a_dict_key(self):
        # __eq__ raises, which blanks __hash__ unless restored; identity
        # hashing is deliberate (ADR 0003) so nodes stay dict-keyable.
        node = ComponentNode(Leaf(text="c"), field_name="content")

        table = {node: "value"}

        assert table[node] == "value"

    def test_two_nodes_wrapping_the_same_child_hash_apart(self):
        leaf = Leaf(text="c")
        first = ComponentNode(leaf, field_name="content")
        second = ComponentNode(leaf, field_name="content")

        assert hash(first) != hash(second)
        assert len({first, second}) == 2


class TestStringifyingFilterGap:
    """Filters that call str() before failing bypass the dunder path.

    ADR 0003 asks these to raise the same targeted error; today they fall
    through to the default object repr instead. Pinned as-is here — see the
    gap note in docs/superpowers/rebuild/adr/0003-slot-opacity.md and the
    ComponentNode docstring. Fixing it is not this subtask's job.
    """

    @pytest.mark.parametrize("filter_name", ["upper", "trim", "striptags"])
    def test_a_stringifying_filter_does_not_raise_today(self, filter_name):
        output = render_expr("{{ content|%s }}" % filter_name, opaque_card())

        assert "ComponentNode" in output.replace("COMPONENTNODE", "ComponentNode")

    def test_the_stringified_output_is_the_repr_not_the_childs_markup(self):
        output = render_expr("{{ content|upper }}", opaque_card())

        assert "COMPONENTNODE(" in output
        assert "LEAF" in output
        assert "<span" not in output


class TestInferenceWithDirectNesting:
    def card_class(self):
        """A Card whose children target is inferred, with a second slot beside it.

        `content` wins children inference by name; `header` is filled by a
        direct Python assignment. The inferred name is read off the auto-built
        descriptor and fed back into the fixture-pointing one, so inference
        stays load-bearing here.
        """

        class Card(BaseComponent):
            content: Slot = ""
            header: Slot = ""

        inferred = Card.__pjx_descriptor__.children_field
        Card.__pjx_descriptor__ = descriptor(
            "slot_header_content.html",
            frozenset({"content", "header"}),
            inferred,
        )
        return Card

    def test_content_is_the_inferred_children_field(self):
        assert self.card_class().__pjx_descriptor__.children_field == "content"

    def test_both_slots_resolve_in_one_render_pass(self):
        Card = self.card_class()

        output = render(
            Card(header=Leaf(text="h"), content=Leaf(text="c")), session()
        )

        assert output == (
            '<div class="card"><header><span class="leaf">h</span></header>'
            '<span class="leaf">c</span></div>'
        )

    def test_each_slot_enters_segments_as_its_own_nested_level(self):
        from pyjinhx2.segments import RenderedLevel

        Card = self.card_class()

        level = render_level(
            Card(header=Leaf(text="h"), content=Leaf(text="c")), session()
        )

        assert len([s for s in level.segments if isinstance(s, RenderedLevel)]) == 2

    def test_the_inferred_field_is_opaque(self):
        Card = self.card_class()
        card = Card(header=Leaf(text="h"), content=Leaf(text="c"))

        with pytest.raises(TypeError, match=r"slot 'content' holds a rendered"):
            render_expr("{{ content|length }}", card)

    def test_the_directly_nested_field_is_opaque(self):
        Card = self.card_class()
        card = Card(header=Leaf(text="h"), content=Leaf(text="c"))

        with pytest.raises(TypeError, match=r"slot 'header' holds a rendered"):
            render_expr("{{ header|length }}", card)

    def test_both_fields_stay_truthy_and_interpolable(self):
        Card = self.card_class()
        card = Card(header=Leaf(text="h"), content=Leaf(text="c"))

        assert render_expr("{% if header and content %}both{% endif %}", card) == "both"


class Titled(BaseComponent):
    title: str = "x"


Titled.__pjx_descriptor__ = descriptor("slot_leaf.html", frozenset())


class TestCollectionsMatrix:
    def card_class(self, template: str):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(template, frozenset({"content"}))
        return Card

    def test_a_list_slot_interpolates_every_entry(self):
        Card = self.card_class("slot_list.html")

        output = render(
            Card(content=[Titled(title="a"), Titled(title="b")]), session()
        )

        assert output == (
            '<div class="list"><span class="leaf">a</span>'
            '<span class="leaf">b</span></div>'
        )

    def test_a_dict_slot_interpolates_every_value_with_its_key(self):
        Card = self.card_class("slot_dict.html")

        output = render(
            Card(content={"one": Titled(title="a"), "two": Titled(title="b")}),
            session(),
        )

        assert output == (
            '<div class="map"><b>one</b><span class="leaf">a</span>'
            '<b>two</b><span class="leaf">b</span></div>'
        )

    def test_the_list_container_itself_stays_iterable_and_measurable(self):
        # Constraint 4: opacity is per entry; wrapping the container would
        # make `{% for %}` and `|length` over it impossible.
        Card = self.card_class("slot_list.html")
        card = Card(content=[Titled(title="a"), Titled(title="b")])

        assert render_expr("{{ content|length }}", card) == "2"

    def test_the_dict_container_supports_values_iteration(self):
        Card = self.card_class("slot_dict.html")
        card = Card(content={"one": Titled(title="a")})

        rendered = render_expr(
            "{% for v in content.values() %}{% if v %}hit{% endif %}{% endfor %}", card
        )

        assert rendered == "hit"

    def test_a_single_list_entry_is_as_opaque_as_a_scalar_slot(self):
        Card = self.card_class("slot_list_len.html")

        with pytest.raises(TypeError, match=r"slot 'content' holds a rendered"):
            render(Card(content=[Titled(title="a")]), session())

    def test_a_single_dict_entry_is_as_opaque_as_a_scalar_slot(self):
        Card = self.card_class("slot_dict.html")
        card = Card(content={"one": Titled(title="a")})

        with pytest.raises(TypeError, match=r"`\|length`"):
            render_expr(
                "{% for v in content.values() %}{{ v|length }}{% endfor %}", card
            )

    def test_each_entry_is_its_own_node_carrying_the_owner_field_name(self):
        Card = self.card_class("slot_list.html")
        a, b = Titled(title="a"), Titled(title="b")

        value = build_context(Card(content=[a, b]), Card.__pjx_descriptor__)["content"]

        assert type(value) is list
        assert [type(v) for v in value] == [ComponentNode, ComponentNode]
        assert {v.field_name for v in value} == {"content"}
        assert [v.component for v in value] == [a, b]

    def test_props_on_list_entries_expose_only_their_own_fields(self):
        Card = self.card_class("slot_props_list.html")

        output = render(
            Card(content=[Titled(title="a"), Titled(title="b")]), session()
        )

        assert output == '<div class="list"><i>a</i><i>b</i></div>'

    def test_props_on_dict_entries_expose_only_their_own_fields(self):
        Card = self.card_class("slot_props_dict.html")

        output = render(Card(content={"one": Titled(title="a")}), session())

        assert output == '<div class="map"><b>one</b><i>a</i></div>'

    def test_an_entrys_props_do_not_leak_a_sibling_entrys_values(self):
        Card = self.card_class("slot_props_list.html")
        a, b = Titled(title="a"), Titled(title="b")

        value = build_context(Card(content=[a, b]), Card.__pjx_descriptor__)["content"]

        assert value[0].props.title == "a"
        assert value[1].props.title == "b"
