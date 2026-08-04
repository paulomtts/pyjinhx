"""Which declared field receives a PascalCase tag's body content (#369).

Field selection only: nothing here renders, mounts a tag, or splices content.
"""

from typing import Annotated, ClassVar

import pytest

from pyjinhx._component import (
    BaseComponent,
    Children,
    PjxSlot,
    Slot,
    _resolve_children_field,
    _resolve_class_descriptor,
)


class TestNoTarget:
    def test_no_slot_fields_resolves_to_none(self):
        class Plain(BaseComponent):
            title: str = ""

        assert Plain.__pjx_descriptor__.children_field is None


class TestFlaggedField:
    def test_single_flagged_field_wins_whatever_its_name(self):
        class Panel(BaseComponent):
            body: Children = ""

        assert Panel.__pjx_descriptor__.children_field == "body"

    def test_flagged_field_beats_a_field_named_content(self):
        class Panel(BaseComponent):
            body: Children = ""
            content: str = ""

        assert Panel.__pjx_descriptor__.children_field == "body"

    def test_two_flagged_fields_raise(self):
        with pytest.raises(ValueError, match="multiple fields flagged"):

            class Panel(BaseComponent):
                left: Children = ""
                right: Children = ""


class TestContentAndBareSlots:
    def test_field_named_content_is_the_target(self):
        class Card(BaseComponent):
            content: str = ""

        assert Card.__pjx_descriptor__.children_field == "content"

    def test_single_bare_slot_is_the_target(self):
        class Card(BaseComponent):
            inner: Slot = ""

        assert Card.__pjx_descriptor__.children_field == "inner"

    def test_two_bare_slots_are_ambiguous_and_resolve_to_none(self):
        class Card(BaseComponent):
            header: Slot = ""
            footer: Slot = ""

        assert Card.__pjx_descriptor__.children_field is None

    def test_content_beats_a_bare_slot(self):
        class Card(BaseComponent):
            content: str = ""
            inner: Slot = ""

        assert Card.__pjx_descriptor__.children_field == "content"


class TestOverride:
    def test_override_selects_the_named_field(self):
        class Card(BaseComponent):
            body: str = ""
            content: str = ""

            _pjx_children_field: ClassVar[str | None] = "body"

        assert Card.__pjx_descriptor__.children_field == "body"

    def test_override_conflicting_with_a_flagged_field_raises(self):
        with pytest.raises(ValueError, match="conflicts with"):

            class Card(BaseComponent):
                body: str = ""
                other: Children = ""

                _pjx_children_field: ClassVar[str | None] = "body"

    def test_override_matching_the_flagged_field_is_fine(self):
        class Card(BaseComponent):
            body: Children = ""

            _pjx_children_field: ClassVar[str | None] = "body"

        assert Card.__pjx_descriptor__.children_field == "body"

    def test_override_naming_an_undeclared_field_is_allowed(self):
        class Card(BaseComponent):
            title: str = ""

            _pjx_children_field: ClassVar[str | None] = "nowhere"

        assert Card.__pjx_descriptor__.children_field == "nowhere"
        assert "nowhere" not in Card.__pjx_descriptor__.slot_fields

    def test_subclass_inherits_the_override_through_the_mro(self):
        class Parent(BaseComponent):
            body: str = ""

            _pjx_children_field: ClassVar[str | None] = "body"

        class Child(Parent):
            pass

        assert Child.__pjx_descriptor__.children_field == "body"

    def test_subclass_can_redeclare_its_own_override(self):
        class Parent(BaseComponent):
            body: str = ""
            other: str = ""

            _pjx_children_field: ClassVar[str | None] = "body"

        class Child(Parent):
            _pjx_children_field: ClassVar[str | None] = "other"

        assert Child.__pjx_descriptor__.children_field == "other"


class TestConsistency:
    def test_a_declared_children_field_is_also_a_slot_field(self):
        class Card(BaseComponent):
            body: Children = ""

        descriptor = Card.__pjx_descriptor__
        assert descriptor.children_field in descriptor.slot_fields

    def test_an_override_named_field_is_also_a_slot_field(self):
        class Card(BaseComponent):
            body: str = ""

            _pjx_children_field: ClassVar[str | None] = "body"

        descriptor = Card.__pjx_descriptor__
        assert descriptor.children_field == "body"
        assert "body" in descriptor.slot_fields

    def test_marker_carried_through_annotated_metadata_directly(self):
        class Card(BaseComponent):
            body: Annotated[str, PjxSlot(children=True)] = ""

        assert Card.__pjx_descriptor__.children_field == "body"


class TestComputedOnce:
    def test_descriptor_is_the_cached_object_not_recomputed(self):
        class Card(BaseComponent):
            body: Children = ""

        assert Card.__pjx_descriptor__ is Card.__pjx_descriptor__

    def test_recomputing_yields_the_same_children_field(self):
        class Card(BaseComponent):
            body: Children = ""

        fresh = _resolve_class_descriptor(Card)
        assert fresh is not Card.__pjx_descriptor__
        assert fresh.children_field == Card.__pjx_descriptor__.children_field == "body"

    def test_resolver_is_pure_and_repeatable(self):
        class Card(BaseComponent):
            body: Children = ""

        assert _resolve_children_field(Card) == _resolve_children_field(Card) == "body"
