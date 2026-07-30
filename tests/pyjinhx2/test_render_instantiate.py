from typing import ClassVar

import pytest
from pydantic import ValidationError

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent, Children, Slot, _pascal_to_snake
from pyjinhx2.render import _children_field
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
