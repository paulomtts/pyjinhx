"""L1.3.6 — the `.props` read-only view on a slot's ComponentNode (#372).

`.props` is ADR 0003's single sanctioned escape hatch: it reads the child
component's already-validated field values and never touches its rendered
output.
"""

from pathlib import Path

import pytest
from pydantic import BaseModel

from pyjinhx.component import BaseComponent, Children, Slot
from pyjinhx.descriptor import ClassDescriptor


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


class Leaf(BaseComponent):
    title: str = "x"
    count: int = 0


Leaf.__pjx_descriptor__ = descriptor("slot_leaf.html", frozenset())


class TestPjxProps:
    def test_it_returns_the_declared_field_values(self):
        leaf = Leaf(title="hello", count=3)

        props = leaf.pjx_props()

        assert props["title"] == "hello"
        assert props["count"] == 3

    def test_it_includes_the_id_field(self):
        leaf = Leaf(id="leaf-1")

        assert leaf.pjx_props()["id"] == "leaf-1"

    def test_a_component_valued_field_stays_the_live_instance(self):
        class Card(BaseComponent):
            content: Slot = ""

        leaf = Leaf(title="inner")
        card = Card(content=leaf)

        assert card.pjx_props()["content"] is leaf

    def test_a_list_of_components_stays_a_list_of_instances(self):
        class Card(BaseComponent):
            content: Slot = ""

        a, b = Leaf(title="a"), Leaf(title="b")
        card = Card(content=[a, b])

        props = card.pjx_props()

        assert props["content"] == [a, b]
        assert props["content"][0] is a

    def test_a_dict_of_components_stays_a_dict_of_instances(self):
        class Card(BaseComponent):
            content: Slot = ""

        a = Leaf(title="a")
        card = Card(content={"one": a})

        assert card.pjx_props()["content"]["one"] is a

    def test_a_children_field_behaves_like_any_other_slot_field(self):
        class Wrap(BaseComponent):
            inner: Children = ""

        leaf = Leaf(title="deep")

        assert Wrap(inner=leaf).pjx_props()["inner"] is leaf

    def test_a_plain_nested_basemodel_is_dumped(self):
        class Meta(BaseModel):
            author: str

        class Article(BaseComponent):
            meta: Meta

        props = Article(meta=Meta(author="ada")).pjx_props()

        assert props["meta"] == {"author": "ada"}

    def test_the_returned_dict_is_a_fresh_copy(self):
        leaf = Leaf(title="hello")

        props = leaf.pjx_props()
        props["title"] = "mutated"

        assert leaf.title == "hello"
        assert leaf.pjx_props()["title"] == "hello"


class TestSlotPropsView:
    def node(self, component: BaseComponent):
        from pyjinhx.markers import ComponentNode

        return ComponentNode(
            component,
            owner_name="Card",
            owner_template=Path("slot_props.html"),
            field_name="content",
        )

    def test_attribute_access_returns_the_validated_value(self):
        assert self.node(Leaf(title="hello")).props.title == "hello"

    def test_attribute_access_preserves_the_python_type(self):
        value = self.node(Leaf(count=3)).props.count

        assert value == 3
        assert type(value) is int

    def test_subscript_access_is_equivalent_to_attribute_access(self):
        props = self.node(Leaf(title="hello")).props

        assert props["title"] == props.title

    def test_an_unknown_attribute_raises_attribute_error(self):
        props = self.node(Leaf(title="hello")).props

        with pytest.raises(AttributeError):
            _ = props.nope

    def test_an_unknown_key_raises_key_error(self):
        props = self.node(Leaf(title="hello")).props

        with pytest.raises(KeyError):
            props["nope"]

    def test_an_unknown_name_does_not_raise_the_opacity_type_error(self):
        # `.props` is the sanctioned escape hatch, so a typo there is an
        # ordinary lookup failure, not ADR 0003's opacity error.
        props = self.node(Leaf(title="hello")).props

        with pytest.raises(AttributeError) as excinfo:
            _ = props.nope
        assert not isinstance(excinfo.value, TypeError)

    def test_str_raises_the_opacity_error(self):
        props = self.node(Leaf(title="hello")).props

        with pytest.raises(TypeError, match=r"slot 'content' holds a rendered"):
            str(props)

    def test_len_is_not_supported(self):
        props = self.node(Leaf(title="hello")).props

        with pytest.raises(TypeError):
            len(props)  # pyright: ignore[reportArgumentType]

    def test_iteration_is_not_supported(self):
        props = self.node(Leaf(title="hello")).props

        with pytest.raises(TypeError):
            list(props)  # pyright: ignore[reportCallIssue, reportArgumentType]

    def test_the_view_is_read_only(self):
        props = self.node(Leaf(title="hello")).props

        with pytest.raises(AttributeError):
            props.title = "mutated"

    def test_repr_is_safe_for_debugging(self):
        props = self.node(Leaf(title="hello")).props

        assert "SlotProps" in repr(props)

    def test_a_component_valued_prop_comes_back_wrapped(self):
        from pyjinhx.markers import ComponentNode

        class Card(BaseComponent):
            content: Slot = ""

        leaf = Leaf(title="inner")

        nested = self.node(Card(content=leaf)).props.content

        assert type(nested) is ComponentNode
        assert nested.component is leaf

    def test_a_component_valued_prop_is_wrapped_through_subscript_too(self):
        from pyjinhx.markers import ComponentNode

        class Card(BaseComponent):
            content: Slot = ""

        leaf = Leaf(title="inner")

        assert type(self.node(Card(content=leaf)).props["content"]) is ComponentNode

    def test_the_nested_node_names_the_props_path_in_its_error(self):
        class Card(BaseComponent):
            content: Slot = ""

        nested = self.node(Card(content=Leaf(title="inner"))).props.content

        with pytest.raises(TypeError) as excinfo:
            str(nested)

        assert "slot 'content.props.content'" in str(excinfo.value)

    def test_the_nested_node_is_opaque_to_every_forbidden_operation(self):
        class Card(BaseComponent):
            content: Slot = ""

        nested = self.node(Card(content=Leaf(title="inner"))).props.content

        with pytest.raises(TypeError, match=r"\.props\.content"):
            str(nested)
        with pytest.raises(TypeError, match=r"\.props\.content"):
            len(nested)  # pyright: ignore[reportArgumentType]
        with pytest.raises(TypeError, match=r"\.props\.content"):
            list(nested)  # pyright: ignore[reportCallIssue, reportArgumentType]
        with pytest.raises(TypeError, match=r"\.props\.content"):
            nested[1:2]  # pyright: ignore[reportIndexIssue]

    def test_a_non_component_prop_is_still_returned_raw(self):
        props = self.node(Leaf(title="hello", count=3)).props

        assert props.title == "hello"
        assert type(props.title) is str
        assert type(props.count) is int

    def test_a_nested_props_hop_keeps_working(self):
        class Card(BaseComponent):
            content: Slot = ""

        nested = self.node(Card(content=Leaf(title="inner"))).props.content

        assert nested.props.title == "inner"  # pyright: ignore[reportAttributeAccessIssue]

    def test_the_nodes_own_forbidden_ops_are_unchanged(self):
        node = self.node(Leaf(title="hello"))

        with pytest.raises(TypeError, match=r"slot 'content' holds a rendered"):
            len(node)  # pyright: ignore[reportArgumentType]
        with pytest.raises(TypeError, match=r"slot 'content' holds a rendered"):
            list(node)  # pyright: ignore[reportCallIssue, reportArgumentType]
        assert bool(node) is True


class TestPropsThroughJinja:
    def session(self):
        from pyjinhx.session import RenderSession

        return RenderSession(template_dir="tests/templates")

    def card_class(self, template: str):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(template, frozenset({"content"}))
        return Card

    def test_a_props_field_renders_its_validated_value(self):
        from pyjinhx.rendering import render

        Card = self.card_class("slot_props.html")

        output = render(Card(content=Leaf(title="hello")), self.session())

        assert output == '<div class="box">hello</div>'

    def test_a_props_value_is_escaped_like_ordinary_text(self):
        # `.props` hands back a plain str, so autoescape applies: only the
        # bare `{{ field }}` path is exempt from escaping.
        from pyjinhx.rendering import render

        Card = self.card_class("slot_props.html")

        output = render(Card(content=Leaf(title="<b>x</b>")), self.session())

        assert output == '<div class="box">&lt;b&gt;x&lt;/b&gt;</div>'

    def test_reading_props_does_not_render_the_child(self):
        import pyjinhx.rendering as render_module

        Card = self.card_class("slot_props.html")
        seen: list[str] = []
        original = render_module.render_level

        def spy(component, session_, chain=()):
            seen.append(type(component).__name__)
            return original(component, session_, chain)

        render_module.render_level = spy
        try:
            render_module.render_level(
                Card(content=Leaf(title="hello")), self.session()
            )
        finally:
            render_module.render_level = original

        assert seen == ["Card"]

    def test_reading_props_produces_no_slot_token(self):
        from pyjinhx.rendering import render_level

        Card = self.card_class("slot_props.html")

        level = render_level(Card(content=Leaf(title="hello")), self.session())
        text = "".join(s for s in level.segments if isinstance(s, str))

        assert "pjx-slot-" not in text

    def test_reading_props_creates_no_nested_rendered_level(self):
        from pyjinhx.rendering import render_level
        from pyjinhx.segments import RenderedLevel

        Card = self.card_class("slot_props.html")

        level = render_level(Card(content=Leaf(title="hello")), self.session())

        assert [s for s in level.segments if isinstance(s, RenderedLevel)] == []

    def test_interpolating_the_view_itself_raises_the_opacity_error(self):
        from pyjinhx.rendering import render

        Card = self.card_class("slot_props_bare_view.html")

        with pytest.raises(
            TypeError, match=r"slot 'content' holds a rendered component"
        ):
            render(Card(content=Leaf(title="hello")), self.session())


class TestPropsRegressions:
    def session(self):
        from pyjinhx.session import RenderSession

        return RenderSession(template_dir="tests/templates")

    def card_class(self, template: str):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(template, frozenset({"content"}))
        return Card

    def test_bare_interpolation_still_splices_the_child(self):
        from pyjinhx.rendering import render

        Card = self.card_class("slot_interp.html")

        output = render(Card(content=Leaf(title="a")), self.session())

        assert output == (
            '<div class="box">before <span class="leaf">a</span> after</div>'
        )

    def test_truthiness_still_takes_the_present_branch(self):
        from pyjinhx.rendering import render

        Card = self.card_class("slot_if.html")

        assert render(Card(content=Leaf(title="a")), self.session()) == "<div>HAS</div>"

    def test_truthiness_still_takes_the_absent_branch(self):
        from pyjinhx.rendering import render

        Card = self.card_class("slot_if.html")

        assert render(Card(content=""), self.session()) == "<div>NONE</div>"

    def test_props_works_on_a_list_wrapped_entry(self):
        from pyjinhx.rendering import render

        Card = self.card_class("slot_props_list.html")

        output = render(
            Card(content=[Leaf(title="a"), Leaf(title="b")]), self.session()
        )

        assert output == '<div class="list"><i>a</i><i>b</i></div>'

    def test_props_works_on_a_dict_wrapped_entry(self):
        from pyjinhx.rendering import render

        Card = self.card_class("slot_props_dict.html")

        output = render(Card(content={"one": Leaf(title="a")}), self.session())

        assert output == '<div class="map"><b>one</b><i>a</i></div>'

    def test_wrapping_still_happens_in_build_context_unchanged(self):
        # `.props` reads the component reference the node already carries, so
        # the wrapping layer needed no change; this pins that.
        from pyjinhx.markers import ComponentNode
        from pyjinhx.render_context import build_context

        Card = self.card_class("slot_props.html")
        leaf = Leaf(title="hello")

        context = build_context(Card(content=leaf), Card.__pjx_descriptor__)

        assert type(context["content"]) is ComponentNode
        assert context["content"].component is leaf
        assert context["content"].props.title == "hello"

    def test_a_nested_component_valued_prop_is_opaque_not_raw(self):
        from pyjinhx.markers import ComponentNode
        from pyjinhx.render_context import build_context

        class Wrap(BaseComponent):
            inner: Children = ""

        Wrap.__pjx_descriptor__ = descriptor(
            "nest_wrap.html", frozenset({"inner"}), "inner"
        )
        Card = self.card_class("slot_props.html")
        leaf = Leaf(title="deep")

        context = build_context(Card(content=Wrap(inner=leaf)), Card.__pjx_descriptor__)
        nested = context["content"].props.inner

        assert type(nested) is ComponentNode
        assert nested.component is leaf
        with pytest.raises(TypeError, match=r"slot 'content\.props\.inner'"):
            str(nested)


class TestStringSlotThroughProps:
    """The `.props` escape hatch must not re-escape a slot's authored markup."""

    def test_a_string_slot_field_comes_back_as_markup(self):
        from markupsafe import Markup

        class Card(BaseComponent):
            body: Slot = ""

        props = Card(body="<b>hi</b>").pjx_props()

        assert isinstance(props["body"], Markup)
        assert props["body"] == "<b>hi</b>"

    def test_a_string_children_field_comes_back_as_markup(self):
        from markupsafe import Markup

        class Card(BaseComponent):
            body: Children = ""

        assert isinstance(Card(body="<b>hi</b>").pjx_props()["body"], Markup)

    def test_a_non_slot_string_field_stays_a_plain_str(self):
        from markupsafe import Markup

        class Card(BaseComponent):
            label: str = ""

        value = Card(label="<b>hi</b>").pjx_props()["label"]

        assert not isinstance(value, Markup)
        assert value == "<b>hi</b>"

    def test_props_reads_the_string_slot_unescaped_through_a_node(self):
        from pyjinhx.render_context import build_context

        class Inner(BaseComponent):
            body: Slot = ""

        Inner.__pjx_descriptor__ = descriptor("slot_leaf.html", frozenset({"body"}))

        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "nest_content.html", frozenset({"content"})
        )

        card = Card(content=Inner(body="<b>hi</b>"))
        context = build_context(card, Card.__pjx_descriptor__)

        body = context["content"].props.body
        assert body == "<b>hi</b>"
        assert body.__html__() == "<b>hi</b>"  # pyright: ignore[reportAttributeAccessIssue]
