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


def test_pipe_none_annotation_becomes_optional():
    assert parse_props_header("{#def value: str | None #}") == [
        ("value", str | None, ...)
    ]


def test_none_pipe_t_annotation_becomes_optional():
    """Order does not matter: ``None | str`` is the same type as ``str | None``."""
    assert parse_props_header("{#def value: None | str #}") == [
        ("value", str | None, ...)
    ]


def test_optional_subscript_becomes_the_same_union():
    assert parse_props_header("{#def value: Optional[int] #}") == [
        ("value", int | None, ...)
    ]


@pytest.mark.parametrize(
    "source_default, expected",
    [
        ('"primary"', "primary"),
        ("0", 0),
        ("1.5", 1.5),
        ("True", True),
        ("None", None),
        ("[1, 2]", [1, 2]),
        ('{"a": 1}', {"a": 1}),
    ],
)
def test_literal_default_is_captured_instead_of_ellipsis(
    source_default: str, expected: Any
):
    fields = parse_props_header(f"{{#def value = {source_default} #}}")
    assert fields is not None
    name, _annotation, default = fields[0]
    assert (name, default) == ("value", expected)


def test_required_and_defaulted_props_mix_in_declared_order():
    assert parse_props_header(
        '{#def title: str, count: int = 0, variant: str = "primary" #}'
    ) == [
        ("title", str, ...),
        ("count", int, 0),
        ("variant", str, "primary"),
    ]


def test_duplicate_prop_name_is_rejected():
    with pytest.raises(ValueError, match="duplicate prop 'title'"):
        parse_props_header("{#def title: str, title: int #}")


@pytest.mark.parametrize(
    "signature",
    ["*args", "**kwargs", "*, x: int", "x, /", "title: str, *rest"],
)
def test_non_simple_parameters_are_rejected(signature: str):
    """Props are plain named keywords — varargs and slot markers have no meaning."""
    with pytest.raises(ValueError, match="simple named props"):
        parse_props_header(f"{{#def {signature} #}}")


def test_non_literal_default_is_rejected():
    with pytest.raises(ValueError, match="default for 'x' must be a literal"):
        parse_props_header("{#def x: int = some_call() #}")


def test_name_reference_default_is_rejected():
    """A bare name would need evaluation; the parser never executes header code."""
    with pytest.raises(ValueError, match="default for 'x' must be a literal"):
        parse_props_header("{#def x: int = DEFAULT_X #}")


def test_malformed_signature_is_rejected():
    with pytest.raises(ValueError, match="invalid"):
        parse_props_header("{#def title: str = ( #}")


def test_header_may_span_multiple_lines_and_carry_extra_whitespace():
    source = """

    {#def
        title: str,
        count: int = 0
    #}
    <div>{{ title }}</div>
    """
    assert parse_props_header(source) == [("title", str, ...), ("count", int, 0)]


def test_header_after_leading_content_is_not_a_header():
    """Only a leading header is out-of-band config; later ones are plain comments."""
    assert parse_props_header("<div></div>{#def title: str #}") is None


def test_a_plain_jinja_comment_is_not_a_header():
    assert parse_props_header("{# just a comment #}<div></div>") is None
