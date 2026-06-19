from markupsafe import Markup

from pyjinhx import BaseComponent, Slot
from pyjinhx.base import _is_slot_field


class _Demo(BaseComponent):
    label: str = ""               # scalar
    body: Slot = ""               # explicit slot
    _pjx_children_field = "kids"
    kids: str = ""                # children field (auto-slot)


def test_is_slot_field_detects_annotation_and_children_field():
    assert _is_slot_field(_Demo, "body") is True
    assert _is_slot_field(_Demo, "kids") is True
    assert _is_slot_field(_Demo, "label") is False


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
