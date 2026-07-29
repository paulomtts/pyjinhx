from typing import Annotated, ClassVar

from pyjinhx2.component import BaseComponent, Children, PjxSlot, Slot, _is_slot_field


class TestPjxSlotMarker:
    def test_children_flag_defaults_to_false(self):
        assert PjxSlot().children is False

    def test_children_flag_opts_in(self):
        assert PjxSlot(children=True).children is True

    def test_marker_instances_are_distinct_objects(self):
        assert PjxSlot() is not PjxSlot()


class TestSlotAliases:
    def test_slot_alias_carries_an_unflagged_marker(self):
        from typing import get_args

        from pyjinhx2.component import Slot

        markers = [m for m in get_args(Slot) if isinstance(m, PjxSlot)]
        assert len(markers) == 1
        assert markers[0].children is False

    def test_children_alias_carries_a_flagged_marker(self):
        from typing import get_args

        from pyjinhx2.component import Children

        markers = [m for m in get_args(Children) if isinstance(m, PjxSlot)]
        assert len(markers) == 1
        assert markers[0].children is True

    def test_slot_alias_underlying_type_is_the_str_component_union(self):
        from typing import get_args

        from pyjinhx2.component import BaseComponent, Slot

        underlying = get_args(Slot)[0]
        assert set(get_args(underlying)) == {str, BaseComponent}


class _Demo(BaseComponent):
    label: str = ""  # plain scalar, no marker
    count: int = 0  # plain scalar, no marker
    body: Slot = ""  # explicit slot
    inner: Children = ""  # children-flagged slot
    nullable_slot: Annotated[str | BaseComponent | None, PjxSlot()] = None


class _DesignatedChildren(BaseComponent):
    # Must carry an explicit `ClassVar` annotation here. `BaseComponent` does not
    # declare `_pjx_children_field` as a ClassVar (that's L1's job, out of scope
    # for #264 per the note above), so an unannotated `_pjx_children_field = "kids"`
    # gets treated as a private *model* attribute by Pydantic — `Demo._pjx_children_field`
    # then returns a `ModelPrivateAttr` object at the class level, not the plain
    # string "kids", and the `==` check in `_is_slot_field` silently returns False.
    # The explicit `ClassVar[str]` annotation on this subclass sidesteps that
    # without touching `BaseComponent` itself. Verified: without it, this test fails.
    _pjx_children_field: ClassVar[str] = "kids"
    kids: str = ""  # designated children field, no PjxSlot metadata


class TestIsSlotField:
    def test_true_for_explicit_slot_field(self):
        assert _is_slot_field(_Demo, "body") is True

    def test_true_for_children_alias_field(self):
        assert _is_slot_field(_Demo, "inner") is True

    def test_true_for_designated_children_field_without_marker(self):
        assert _is_slot_field(_DesignatedChildren, "kids") is True

    def test_false_for_plain_str_field(self):
        assert _is_slot_field(_Demo, "label") is False

    def test_false_for_plain_int_field(self):
        assert _is_slot_field(_Demo, "count") is False

    def test_false_for_unknown_field_name(self):
        assert _is_slot_field(_Demo, "not_a_field") is False

    def test_true_for_nullable_slot_with_outer_annotation(self):
        # `Slot | None` drops PjxSlot at the field level, so the marker must sit
        # on the OUTER Annotated. This asserts the outer form keeps working.
        assert _is_slot_field(_Demo, "nullable_slot") is True
