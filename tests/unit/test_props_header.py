from typing import Any, Optional

import pytest
from pydantic import ValidationError

from pyjinhx.base import BaseComponent
from pyjinhx.props_header import build_component_model, parse_props_header


def test_no_header_returns_none():
    assert parse_props_header("<div>{{ x }}</div>") is None


def test_parses_names_types_defaults():
    src = '{#def title: str, count: int = 0, variant: str = "primary" #}\n<div></div>'
    assert parse_props_header(src) == [
        ("title", str, ...),
        ("count", int, 0),
        ("variant", str, "primary"),
    ]


def test_untyped_prop_is_any():
    assert parse_props_header("{#def x, y=1 #}") == [("x", Any, ...), ("y", Any, 1)]


def test_optional_via_union():
    assert parse_props_header("{#def note: str | None = None #}") == [
        ("note", Optional[str], None)
    ]


def test_multiline_header():
    src = "{#def\n  title: str,\n  count: int = 0,\n#}\n<div></div>"
    assert parse_props_header(src) == [("title", str, ...), ("count", int, 0)]


def test_non_literal_default_errors():
    with pytest.raises(ValueError, match="must be a literal"):
        parse_props_header("{#def x = some_func() #}")


def test_malformed_signature_errors():
    with pytest.raises(ValueError, match="invalid"):
        parse_props_header("{#def : : : #}")


def test_duplicate_prop_errors():
    with pytest.raises(ValueError, match="duplicate"):
        parse_props_header("{#def x, x = 1 #}")


def test_build_model_validates_required_and_coerces():
    src = '{#def title: str, count: int = 0 #}\n<div>{{ title }}</div>'
    model = build_component_model("CardBuildA", src)
    assert model is not None
    assert issubclass(model, BaseComponent)
    assert model._pjx_template == "CardBuildA"
    inst = model(id="i", title="Hi", count="3")  # "3" coerced to int
    assert inst.count == 3  # type: ignore[attr-defined]  # count is a header-defined field
    with pytest.raises(ValidationError):
        model(id="i")  # missing required 'title'


def test_build_model_none_without_header():
    assert build_component_model("CardBuildB", "<div></div>") is None
