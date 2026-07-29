from pyjinhx2.component import PjxSlot


class TestPjxSlotMarker:
    def test_children_flag_defaults_to_false(self):
        assert PjxSlot().children is False

    def test_children_flag_opts_in(self):
        assert PjxSlot(children=True).children is True

    def test_marker_instances_are_distinct_objects(self):
        assert PjxSlot() is not PjxSlot()
