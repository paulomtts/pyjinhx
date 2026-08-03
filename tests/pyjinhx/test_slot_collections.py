"""L1.3.5 — a slot field holding a list or dict of components (#371).

Each component entry is opaque on its own (ADR 0003); the list/dict container
itself stays an ordinary Python value so `{% for %}` can walk it.
"""

from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from pyjinhx.component import BaseComponent, Children, Slot
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.markers import ComponentNode
from pyjinhx.render import render
from pyjinhx.render_context import build_context
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
    title: str = "x"


Leaf.__pjx_descriptor__ = descriptor("slot_leaf.html", frozenset())


class TestAliasUnion:
    def test_slot_union_admits_list_and_dict_of_components(self):
        underlying = get_args(Slot)[0]
        assert set(get_args(underlying)) == {
            str,
            BaseComponent,
            list[BaseComponent],
            dict[str, BaseComponent],
        }

    def test_children_union_admits_list_and_dict_of_components(self):
        underlying = get_args(Children)[0]
        assert set(get_args(underlying)) == {
            str,
            BaseComponent,
            list[BaseComponent],
            dict[str, BaseComponent],
        }


class TestConstruction:
    def test_a_list_of_components_is_accepted_by_identity(self):
        class Card(BaseComponent):
            content: Slot = ""

        a, b = Leaf(title="a"), Leaf(title="b")
        card = Card(content=[a, b])

        assert card.content == [a, b]
        assert card.content[0] is a  # pyright: ignore[reportIndexIssue, reportArgumentType]

    def test_a_dict_of_components_is_accepted_by_identity(self):
        class Card(BaseComponent):
            content: Slot = ""

        a = Leaf(title="a")
        card = Card(content={"one": a})

        assert card.content == {"one": a}

    def test_an_empty_list_is_accepted(self):
        class Card(BaseComponent):
            content: Slot = ""

        assert Card(content=[]).content == []

    def test_an_empty_dict_is_accepted(self):
        class Card(BaseComponent):
            content: Slot = ""

        assert Card(content={}).content == {}

    def test_a_children_field_accepts_a_list_too(self):
        class Wrap(BaseComponent):
            inner: Children = ""

        a = Leaf(title="a")
        assert Wrap(inner=[a]).inner == [a]

    def test_a_string_entry_inside_a_list_is_rejected(self):
        # Locked decision: list/dict members are components only. A bare string
        # entry has no slot semantics of its own, so it fails at construction.
        class Card(BaseComponent):
            content: Slot = ""

        with pytest.raises(ValidationError):
            Card(content=[Leaf(title="a"), "raw"])  # pyright: ignore[reportIndexIssue, reportArgumentType]

    def test_a_string_entry_inside_a_dict_is_rejected(self):
        class Card(BaseComponent):
            content: Slot = ""

        with pytest.raises(ValidationError):
            Card(content={"k": "raw"})  # pyright: ignore[reportIndexIssue, reportArgumentType]

    def test_a_non_string_dict_key_is_rejected_at_construction(self):
        class Card(BaseComponent):
            content: Slot = ""

        with pytest.raises(ValidationError):
            Card(content={1: Leaf(title="a")})  # pyright: ignore[reportIndexIssue, reportArgumentType]

    def test_a_json_looking_string_still_stays_a_plain_string(self):
        # The list/dict members must not open a JSON-coercion path: a union that
        # still contains `str` stays exempt, so markup-looking JSON round-trips.
        class Card(BaseComponent):
            content: Slot = ""

        raw = '["not", "a", "list"]'
        assert Card(content=raw).content == raw
        assert type(Card(content=raw).content) is str


class TestBuildContext:
    def test_a_list_slot_stays_a_list_of_nodes(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))
        a, b = Leaf(title="a"), Leaf(title="b")

        context = build_context(Card(content=[a, b]), Card.__pjx_descriptor__)
        value = context["content"]

        assert type(value) is list
        assert not isinstance(value, ComponentNode)
        assert [type(v) for v in value] == [ComponentNode, ComponentNode]
        assert [v.component for v in value] == [a, b]

    def test_a_dict_slot_keeps_plain_keys_and_wraps_values(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_dict.html", frozenset({"content"}))
        a = Leaf(title="a")

        context = build_context(Card(content={"one": a}), Card.__pjx_descriptor__)
        value = context["content"]

        assert type(value) is dict
        assert list(value.keys()) == ["one"]
        assert type(value["one"]) is ComponentNode
        assert value["one"].component is a

    def test_each_entry_node_carries_owner_identity_for_error_messages(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        context = build_context(
            Card(content=[Leaf(title="a")]), Card.__pjx_descriptor__
        )
        node = context["content"][0]

        assert node.owner_name == "Card"
        assert node.owner_template == Path("slot_list.html")
        assert node.field_name == "content"

    def test_an_empty_list_slot_stays_an_empty_list(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        context = build_context(Card(content=[]), Card.__pjx_descriptor__)

        assert context["content"] == []

    def test_an_empty_dict_slot_stays_an_empty_dict(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_dict.html", frozenset({"content"}))

        context = build_context(Card(content={}), Card.__pjx_descriptor__)

        assert context["content"] == {}

    def test_the_single_component_slot_is_unchanged(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_interp.html", frozenset({"content"}))
        a = Leaf(title="a")

        context = build_context(Card(content=a), Card.__pjx_descriptor__)

        assert type(context["content"]) is ComponentNode
        assert context["content"].component is a

    def test_a_string_slot_is_unchanged(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_interp.html", frozenset({"content"}))

        context = build_context(Card(content="<b>raw</b>"), Card.__pjx_descriptor__)

        assert context["content"] == "<b>raw</b>"

    def test_the_components_own_list_is_not_mutated(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))
        a = Leaf(title="a")
        card = Card(content=[a])

        build_context(card, Card.__pjx_descriptor__)

        assert card.content == [a]
        assert card.content[0] is a  # pyright: ignore[reportIndexIssue, reportArgumentType]


class TestListRendering:
    def test_every_entry_renders_in_declaration_order(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        output = render(Card(content=[Leaf(title="a"), Leaf(title="b")]), session())

        assert output == (
            '<div class="list">'
            '<span class="leaf">a</span><span class="leaf">b</span>'
            "</div>"
        )

    def test_no_marker_or_token_leaks_into_the_output(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        output = render(Card(content=[Leaf(title="a"), Leaf(title="b")]), session())

        assert "ComponentNode" not in output
        assert "pjx-slot-" not in output

    def test_an_empty_list_renders_nothing(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        assert render(Card(content=[]), session()) == '<div class="list"></div>'

    def test_each_entry_enters_segments_as_its_own_rendered_level(self):
        from pyjinhx.render import render_level
        from pyjinhx.segments import RenderedLevel

        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        level = render_level(
            Card(content=[Leaf(title="a"), Leaf(title="b")]), session()
        )

        nested = [s for s in level.segments if isinstance(s, RenderedLevel)]
        assert len(nested) == 2
        # Only the surrounding markup text (which incidentally contains the
        # letters "a"/"b" via class="list") should land in string segments;
        # the actual leaf titles must come from the nested RenderedLevels.
        text = "".join(s for s in level.segments if isinstance(s, str))
        assert ">a<" not in text and ">b<" not in text

    def test_each_entry_is_rendered_exactly_once(self, monkeypatch):
        import pyjinhx.render as render_module

        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        original = render_module.render_level
        seen: list[str] = []

        def spy(component, session_, chain=()):
            seen.append(type(component).__name__)
            return original(component, session_, chain)

        monkeypatch.setattr(render_module, "render_level", spy)

        render_module.render_level(
            Card(content=[Leaf(title="a"), Leaf(title="b")]), session()
        )

        assert seen.count("Leaf") == 2

    def test_the_same_instance_listed_twice_renders_twice(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))
        leaf = Leaf(title="dup")

        output = render(Card(content=[leaf, leaf]), session())

        assert output == (
            '<div class="list">'
            '<span class="leaf">dup</span><span class="leaf">dup</span>'
            "</div>"
        )

    def test_a_nested_component_inside_a_list_entry_still_composes(self):
        class Wrap(BaseComponent):
            inner: Slot = ""

        Wrap.__pjx_descriptor__ = descriptor(
            "nest_wrap.html", frozenset({"inner"}), "inner"
        )

        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        output = render(Card(content=[Wrap(inner=Leaf(title="deep"))]), session())

        assert output == (
            '<div class="list"><section class="wrap">'
            '<span class="leaf">deep</span></section></div>'
        )


class TestDictRendering:
    def test_keys_render_as_text_and_values_render_as_components(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_dict.html", frozenset({"content"}))

        output = render(
            Card(content={"one": Leaf(title="a"), "two": Leaf(title="b")}), session()
        )

        assert output == (
            '<div class="map">'
            '<b>one</b><span class="leaf">a</span>'
            '<b>two</b><span class="leaf">b</span>'
            "</div>"
        )

    def test_a_key_is_escaped_like_any_other_string(self):
        # Invariant 6: only the component values are opaque; keys are ordinary
        # interpolated text and go through autoescape.
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_dict.html", frozenset({"content"}))

        output = render(Card(content={"<x>": Leaf(title="a")}), session())

        assert "<b>&lt;x&gt;</b>" in output
        assert "<b><x></b>" not in output

    def test_an_empty_dict_renders_nothing(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_dict.html", frozenset({"content"}))

        assert render(Card(content={}), session()) == '<div class="map"></div>'

    def test_insertion_order_is_preserved(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_dict.html", frozenset({"content"}))

        output = render(
            Card(content={"z": Leaf(title="z"), "a": Leaf(title="a")}), session()
        )

        assert output.index("<b>z</b>") < output.index("<b>a</b>")


class TestEntryOpacity:
    def test_a_dunder_filter_on_a_list_entry_raises_the_existing_opacity_error(self):
        # Same TypeError builder as the single-component case (ADR 0003 / #368):
        # no new exception type, and the message names the owning field.
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "slot_list_len.html", frozenset({"content"})
        )

        with pytest.raises(
            TypeError, match=r"slot 'content' holds a rendered component"
        ):
            render(Card(content=[Leaf(title="a")]), session())

    def test_the_error_names_the_owning_component_and_template(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor(
            "slot_list_len.html", frozenset({"content"})
        )

        with pytest.raises(TypeError) as excinfo:
            render(Card(content=[Leaf(title="a")]), session())

        message = str(excinfo.value)
        assert "Card" in message
        assert "slot_list_len.html" in message

    def test_a_dict_entry_is_opaque_the_same_way(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_dict.html", frozenset({"content"}))

        context = build_context(
            Card(content={"k": Leaf(title="a")}), Card.__pjx_descriptor__
        )

        with pytest.raises(
            TypeError, match=r"slot 'content' holds a rendered component"
        ):
            len(context["content"]["k"])

    def test_the_container_itself_stays_an_ordinary_python_value(self):
        # Out of scope for opacity by design: only entries are opaque, so
        # length and indexing on the container work like any list.
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_list.html", frozenset({"content"}))

        context = build_context(
            Card(content=[Leaf(title="a"), Leaf(title="b")]), Card.__pjx_descriptor__
        )

        assert len(context["content"]) == 2
        assert type(context["content"][0]) is ComponentNode


class TestCollectionTruthiness:
    def test_a_populated_list_takes_the_truthy_branch(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_if.html", frozenset({"content"}))

        assert render(Card(content=[Leaf(title="a")]), session()) == "<div>HAS</div>"

    def test_an_empty_list_takes_the_falsy_branch(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_if.html", frozenset({"content"}))

        assert render(Card(content=[]), session()) == "<div>NONE</div>"

    def test_a_populated_dict_takes_the_truthy_branch(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_if.html", frozenset({"content"}))

        assert (
            render(Card(content={"k": Leaf(title="a")}), session()) == "<div>HAS</div>"
        )

    def test_an_empty_dict_takes_the_falsy_branch(self):
        class Card(BaseComponent):
            content: Slot = ""

        Card.__pjx_descriptor__ = descriptor("slot_if.html", frozenset({"content"}))

        assert render(Card(content={}), session()) == "<div>NONE</div>"
