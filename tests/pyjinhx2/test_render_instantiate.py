from typing import ClassVar

import pytest
from pydantic import ValidationError

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent, Children, Slot, _pascal_to_snake
from pyjinhx2.render import _children_field, _fill_children, _instantiate_child
from pyjinhx2.segments import ChildRef, RenderedLevel


class Plain(BaseComponent):
    label: str = ""


class WithChildren(BaseComponent):
    body: Children = ""


class WithChildrenVar(BaseComponent):
    _pjx_children_field: ClassVar[str] = "content"
    content: Slot = ""


class TwoChildren(BaseComponent):
    first: Children = ""
    second: Children = ""


def test_children_field_none_when_class_designates_none():
    assert _children_field(Plain) is None


def test_children_field_prefers_children_marker():
    assert _children_field(WithChildren) == "body"


def test_children_field_falls_back_to_class_var():
    assert _children_field(WithChildrenVar) == "content"


def test_children_field_raises_when_two_fields_claim_the_role():
    with pytest.raises(ValueError, match="TwoChildren"):
        _children_field(TwoChildren)


class Scalars(BaseComponent):
    label: str = ""
    variant: str = "primary"


class Structured(BaseComponent):
    rows: list[dict[str, str]] = []


class NoAutoId(BaseComponent):
    auto_id: ClassVar[bool] = False


def test_instantiate_passes_scalar_attrs_through():
    ref = ChildRef(tag="Scalars", attrs={"label": "Save", "variant": "danger"}, inner=None)
    instance = _instantiate_child(ref, Scalars)
    assert isinstance(instance, Scalars)
    assert instance.label == "Save"
    assert instance.variant == "danger"


def test_instantiate_reaches_the_json_coercion_path():
    ref = ChildRef(tag="Structured", attrs={"rows": '[{"a": "1"}]'}, inner=None)
    instance = _instantiate_child(ref, Structured)
    assert instance.rows == [{"a": "1"}]


def test_instantiate_assigns_an_auto_id():
    ref = ChildRef(tag="Scalars", attrs={}, inner=None)
    instance = _instantiate_child(ref, Scalars)
    assert instance.id.startswith("pjx-")


def test_instantiate_keeps_an_explicit_id_attr():
    ref = ChildRef(tag="Scalars", attrs={"id": "save-btn"}, inner=None)
    assert _instantiate_child(ref, Scalars).id == "save-btn"


def test_instantiate_propagates_missing_required_id():
    ref = ChildRef(tag="NoAutoId", attrs={}, inner=None)
    with pytest.raises(ValueError, match="auto_id = False"):
        _instantiate_child(ref, NoAutoId)


def test_instantiate_propagates_validation_error_for_unknown_attr():
    ref = ChildRef(tag="Scalars", attrs={"nope": "x"}, inner=None)
    with pytest.raises(ValidationError):
        _instantiate_child(ref, Scalars)


def test_instantiate_merges_inner_into_the_children_field():
    ref = ChildRef(tag="WithChildren", attrs={}, inner="<em>hi</em>")
    instance = _instantiate_child(ref, WithChildren)
    assert instance.body == "<em>hi</em>"


def test_instantiate_ignores_blank_inner_when_no_children_field():
    ref = ChildRef(tag="Scalars", attrs={"label": "Save"}, inner="\n  ")
    assert _instantiate_child(ref, Scalars).label == "Save"


def test_instantiate_raises_when_inner_has_no_target_field():
    ref = ChildRef(tag="Scalars", attrs={}, inner="<em>hi</em>")
    with pytest.raises(ValueError, match="<Scalars>"):
        _instantiate_child(ref, Scalars)


def test_instantiate_raises_when_inner_and_attr_both_supply_the_field():
    ref = ChildRef(tag="WithChildren", attrs={"body": "attr"}, inner="<em>hi</em>")
    with pytest.raises(ValueError, match="body"):
        _instantiate_child(ref, WithChildren)
