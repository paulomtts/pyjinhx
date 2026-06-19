from typing import Annotated

from markupsafe import Markup

from pyjinhx import BaseComponent, Slot
from pyjinhx.base import PjxSlot, _is_slot_field


class _Demo(BaseComponent):
    label: str = ""               # scalar
    body: Slot = ""               # explicit slot
    nullable_slot: Annotated[str | BaseComponent | None, PjxSlot()] = None
    _pjx_children_field = "kids"
    kids: str = ""                # children field (auto-slot)


def test_is_slot_field_detects_annotation_and_children_field():
    assert _is_slot_field(_Demo, "body") is True
    assert _is_slot_field(_Demo, "kids") is True
    assert _is_slot_field(_Demo, "label") is False


def test_nullable_slot_metadata_survives():
    # `Slot | None` (Optional[Annotated[...]]) drops the PjxSlot metadata at the
    # field level; the marker must sit on the outer Annotated (#118).
    assert _is_slot_field(_Demo, "nullable_slot") is True


def test_accordion_optional_slots_are_detected():
    from pyjinhx.builtins import PJXAccordion

    assert _is_slot_field(PJXAccordion, "header") is True
    assert _is_slot_field(PJXAccordion, "actions") is True


def test_slot_string_value_becomes_markup_in_context(tmp_path):
    from pyjinhx import Renderer
    Renderer.set_default_environment(str(tmp_path))
    inst = _Demo(id="d", label="<x>", body="<b>", kids="<k>")
    ctx = inst.model_dump()  # sanity: model_dump gives plain str
    assert ctx["body"] == "<b>"
    # the builder wraps slot strings as Markup; scalars stay plain str
    built = inst._build_template_context()  # helper exposed for testing (see Step 3)
    assert isinstance(built["body"], Markup)
    assert isinstance(built["kids"], Markup)
    assert not isinstance(built["label"], Markup)
