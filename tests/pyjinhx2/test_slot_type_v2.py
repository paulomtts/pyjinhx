from typing import Annotated, ClassVar

import pytest
from pydantic import ValidationError

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


class _Leaf(BaseComponent):
    text: str = ""


class TestSlotFieldValidation:
    def test_accepts_a_plain_string(self):
        demo = _Demo(body="<b>bold</b>")
        assert demo.body == "<b>bold</b>"
        assert isinstance(demo.body, str)

    def test_does_not_escape_or_wrap_the_string_at_construction(self):
        # L0 is marker-only: no Markup, no escaping, no side effects. The
        # value round-trips byte-for-byte as the plain str that was passed in.
        raw = "<script>alert(1)</script>"
        assert _Demo(body=raw).body == raw
        assert type(_Demo(body=raw).body) is str

    def test_accepts_a_basecomponent_instance(self):
        # Type-level acceptance only; render-time behavior is L1 (ADR 0003).
        leaf = _Leaf(text="hi")
        assert _Demo(body=leaf).body is leaf

    def test_rejects_an_int(self):
        with pytest.raises(ValidationError):
            _Demo(body=1)  # pyright: ignore[reportArgumentType]

    def test_rejects_a_list(self):
        with pytest.raises(ValidationError):
            _Demo(body=["a"])  # pyright: ignore[reportArgumentType]

    def test_slot_field_does_not_weaken_extra_forbid(self):
        assert _Demo.model_config.get("extra") == "forbid"
        with pytest.raises(ValidationError):
            _Demo(body="x", undeclared="y")  # pyright: ignore[reportCallIssue]

    def test_slot_field_default_applies(self):
        assert _Demo().body == ""
        assert _Demo().inner == ""

    def test_children_field_accepts_a_basecomponent_instance_untouched(self):
        # Same guarantee as the Slot case, on the children-flagged alias: the
        # instance passes through by identity, unwrapped and unconverted.
        leaf = _Leaf(text="hi")
        demo = _Demo(inner=leaf)
        assert demo.inner is leaf
        assert type(demo.inner) is _Leaf

    def test_json_looking_string_round_trips_on_slot_and_children(self):
        # Slot/Children are excluded from JSON coercion: a JSON-looking string
        # is almost certainly literal markup, so it survives as a plain str.
        raw = '{"looks": "like json"}'
        assert _Demo(body=raw).body == raw
        assert _Demo(inner=raw).inner == raw
        assert type(_Demo(body=raw).body) is str

    def test_quote_containing_string_round_trips_byte_for_byte(self):
        # No quote-safety validator and no escaping at L0 (ADR 0003): both quote
        # kinds survive verbatim.
        raw = 'he said "hi" and it\'s fine'
        assert _Demo(body=raw).body == raw
        assert type(_Demo(body=raw).body) is str
