from pyjinhx2.component import PjxSlot


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
