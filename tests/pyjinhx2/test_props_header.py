"""Unit tests for the ``{#def ... #}`` header parser.

Parsing only — building a model class from the parsed spec belongs to #376,
so nothing here imports pydantic or pyjinhx2.component.
"""

from typing import Any

import pytest

from pyjinhx2.props_header import parse_props_header


def test_source_without_a_header_returns_none():
    """No header is the common case, not an error — most templates are strict."""
    assert parse_props_header("<div>hello</div>") is None


def test_header_with_no_props_returns_an_empty_list():
    """An empty header still declares the template classless, with zero props."""
    assert parse_props_header("{#def #}<div></div>") == []


def test_unannotated_prop_is_any_and_required():
    assert parse_props_header("{#def title #}") == [("title", Any, ...)]


@pytest.mark.parametrize(
    "annotation, expected",
    [("str", str), ("int", int), ("float", float), ("bool", bool), ("list", list), ("dict", dict)],
)
def test_each_supported_annotation_resolves_to_its_type(annotation: str, expected: type):
    assert parse_props_header(f"{{#def value: {annotation} #}}") == [
        ("value", expected, ...)
    ]


def test_unrecognized_annotation_falls_back_to_any():
    """The vocabulary is deliberately closed: a header cannot import names."""
    assert parse_props_header("{#def value: SomeModel #}") == [("value", Any, ...)]


def test_required_props_keep_their_declared_order():
    assert parse_props_header("{#def title: str, count: int, flag: bool #}") == [
        ("title", str, ...),
        ("count", int, ...),
        ("flag", bool, ...),
    ]
