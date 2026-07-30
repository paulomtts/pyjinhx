from typing import ClassVar, cast

import pytest
from pydantic import Field, ValidationError

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent, Children, Slot, _pascal_to_snake
from pyjinhx2.render import _fill_children, _instantiate_child
from pyjinhx2.segments import ChildRef, RenderedLevel


class Plain(BaseComponent):
    label: str = ""


class WithChildren(BaseComponent):
    body: Children = ""


class WithChildrenVar(BaseComponent):
    _pjx_children_field: ClassVar[str] = "content"
    content: Slot = ""


def test_children_field_none_when_class_designates_none():
    assert Plain.__pjx_descriptor__.children_field is None


def test_children_field_prefers_children_marker():
    assert WithChildren.__pjx_descriptor__.children_field == "body"


def test_children_field_falls_back_to_class_var():
    assert WithChildrenVar.__pjx_descriptor__.children_field == "content"


def test_children_field_raises_when_two_fields_claim_the_role():
    # #369: resolution now happens once at class-registration time (invariant
    # 5), so defining the conflicting class is itself the failure point.
    with pytest.raises(ValueError, match="multiple fields flagged"):

        class TwoChildren(BaseComponent):
            first: Children = ""
            second: Children = ""


class Scalars(BaseComponent):
    label: str = ""
    variant: str = "primary"


class Structured(BaseComponent):
    rows: list[dict[str, str]] = Field(default_factory=list)


class NoAutoId(BaseComponent):
    auto_id: ClassVar[bool] = False


def test_instantiate_passes_scalar_attrs_through():
    ref = ChildRef(
        tag="Scalars", attrs={"label": "Save", "variant": "danger"}, inner=None
    )
    instance = _instantiate_child(ref, Scalars)
    assert isinstance(instance, Scalars)
    assert instance.label == "Save"
    assert instance.variant == "danger"


def test_instantiate_reaches_the_json_coercion_path():
    ref = ChildRef(tag="Structured", attrs={"rows": '[{"a": "1"}]'}, inner=None)
    instance = cast(Structured, _instantiate_child(ref, Structured))
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
    instance = cast(WithChildren, _instantiate_child(ref, WithChildren))
    assert instance.body == "<em>hi</em>"


def test_instantiate_ignores_blank_inner_when_no_children_field():
    ref = ChildRef(tag="Scalars", attrs={"label": "Save"}, inner="\n  ")
    instance = cast(Scalars, _instantiate_child(ref, Scalars))
    assert instance.label == "Save"


def test_instantiate_raises_when_inner_has_no_target_field():
    ref = ChildRef(tag="Scalars", attrs={}, inner="<em>hi</em>")
    with pytest.raises(ValueError, match="<Scalars>"):
        _instantiate_child(ref, Scalars)


def test_instantiate_raises_when_inner_and_attr_both_supply_the_field():
    ref = ChildRef(tag="WithChildren", attrs={"body": "attr"}, inner="<em>hi</em>")
    with pytest.raises(ValueError, match="body"):
        _instantiate_child(ref, WithChildren)


def _level(*segments):
    return RenderedLevel(segments=list(segments), root_span=(0, 0), descriptor=None)


@pytest.fixture
def _registered():
    discovery._registry.mapping = {
        _pascal_to_snake(cls.__name__): cls for cls in (Scalars, WithChildren)
    }
    yield
    discovery._registry.mapping = {}


def test_fill_children_returns_instances_for_resolved_tags(_registered):
    level = _level(
        "<div>", ChildRef(tag="Scalars", attrs={"label": "Save"}, inner=None), "</div>"
    )
    pending = _fill_children(level)
    assert len(pending) == 1
    index, instance = pending[0]
    assert index == 1
    assert isinstance(instance, Scalars)
    assert instance.label == "Save"
    assert isinstance(level.segments[1], ChildRef)


def test_fill_children_reports_document_order(_registered):
    level = _level(
        ChildRef(tag="Scalars", attrs={"label": "one"}, inner=None),
        "mid",
        ChildRef(tag="WithChildren", attrs={}, inner="body"),
    )
    pending = _fill_children(level)
    assert [index for index, _ in pending] == [0, 2]
    assert [type(instance) for _, instance in pending] == [Scalars, WithChildren]


def test_fill_children_never_instantiates_an_unresolved_tag(_registered):
    level = _level(ChildRef(tag="MyWidget", attrs={"nope": "x"}, inner=None))
    assert _fill_children(level) == []
    assert level.segments[0] == '<MyWidget nope="x"/>'
