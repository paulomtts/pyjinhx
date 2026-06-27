"""Per-class resolution of the children target (_pjx_children_target)."""

from typing import Annotated, ClassVar

import pytest

from pyjinhx import BaseComponent, Children, Slot
from pyjinhx.base import PjxSlot, _is_slot_field


def test_sole_slot_field_is_inferred_as_target():
    class SearchFieldRes(BaseComponent):
        filters: Annotated[str | BaseComponent | None, PjxSlot()] = None

    assert SearchFieldRes._pjx_children_target == "filters"
    assert _is_slot_field(SearchFieldRes, "filters") is True


def test_content_field_beats_sole_other_slot():
    class CardRes(BaseComponent):
        content: str = ""
        footer: Slot = ""

    assert CardRes._pjx_children_target == "content"


def test_flag_beats_content_field():
    class PanelRes(BaseComponent):
        content: str = ""
        body: Children = ""

    assert PanelRes._pjx_children_target == "body"


def test_multiple_unflagged_slots_no_content_is_ambiguous():
    class MenuRes(BaseComponent):
        trigger: Slot = ""
        items: Annotated[str | BaseComponent, PjxSlot()] = ""

    assert MenuRes._pjx_children_target is None


def test_no_slots_defaults_to_content():
    class PlainRes(BaseComponent):
        label: str = ""

    assert PlainRes._pjx_children_target == "content"


def test_two_children_flags_raise_at_definition():
    with pytest.raises(ValueError, match="multiple fields flagged"):

        class BadRes(BaseComponent):
            a: Children = ""
            b: Children = ""


def test_override_conflicting_with_flag_raises_at_definition():
    with pytest.raises(ValueError, match="conflicts with"):

        class Bad2Res(BaseComponent):
            _pjx_children_field: ClassVar[str] = "x"
            x: str = ""
            y: Children = ""


def test_explicit_override_wins():
    class BoxedRes(BaseComponent):
        _pjx_children_field: ClassVar[str] = "kids"
        kids: str = ""

    assert BoxedRes._pjx_children_target == "kids"
    assert _is_slot_field(BoxedRes, "kids") is True


def test_subclass_inherits_override_via_mro():
    class Boxed2Res(BaseComponent):
        _pjx_children_field: ClassVar[str] = "kids"
        kids: str = ""

    class SubBoxedRes(Boxed2Res):
        extra: str = ""

    assert SubBoxedRes._pjx_children_target == "kids"
