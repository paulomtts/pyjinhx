"""Unit tests for the ``{#def ... #}`` header parser.

Parsing only — building a model class from the parsed spec belongs to #376,
so nothing here exercises class generation.
"""

import logging
import sys
from typing import Any

import pytest
from jinja2 import TemplateSyntaxError

from pyjinhx.props_header import parse_props_header


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
    [
        ("str", str),
        ("int", int),
        ("float", float),
        ("bool", bool),
        ("list", list),
        ("dict", dict),
    ],
)
def test_each_supported_annotation_resolves_to_its_type(
    annotation: str, expected: type
):
    assert parse_props_header(f"{{#def value: {annotation} #}}") == [
        ("value", expected, ...)
    ]


def test_unrecognized_annotation_falls_back_to_any(caplog):
    """A bare name is never imported, so a typo cannot become an import; the
    warning points at the dotted form that would import it."""
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        fields = parse_props_header("{#def value: SomeModel #}")

    assert fields == [("value", Any, ...)]
    warnings = [
        r for r in caplog.records if "is not a recognized type" in r.getMessage()
    ]
    assert len(warnings) == 1, [r.getMessage() for r in caplog.records]
    assert warnings[0].levelno == logging.WARNING
    message = warnings[0].getMessage()
    assert "value" in message
    assert "SomeModel" in message
    assert "dotted import path" in message


@pytest.mark.parametrize(
    "annotation",
    ["str", "int", "float", "bool", "list", "dict", "Any", "Slot", "Children"],
)
def test_recognized_annotations_do_not_warn(annotation: str, caplog):
    """A name in the closed vocabulary resolved fine — warning about it would
    train authors to ignore the warning that matters."""
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        parse_props_header(f"{{#def value: {annotation} #}}")

    assert [
        r.getMessage()
        for r in caplog.records
        if "is not a recognized type" in r.getMessage()
    ] == []


@pytest.mark.parametrize(
    "annotation", ["SomeModel | None", "None | SomeModel", "Optional[SomeModel]"]
)
def test_unrecognized_inside_optional_warns_exactly_once(annotation: str, caplog):
    """The Name branch is the sole emission point, so wrapping an unresolved
    name in a union reports it once, not once per recursive descent."""
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        parse_props_header(f"{{#def value: {annotation} #}}")

    warnings = [
        r for r in caplog.records if "is not a recognized type" in r.getMessage()
    ]
    assert len(warnings) == 1, [r.getMessage() for r in warnings]
    assert "SomeModel" in warnings[0].getMessage()


@pytest.mark.parametrize(
    "annotation, expected_children",
    [("Slot", False), ("Children", True)],
)
def test_slot_names_resolve_to_the_marker_carrying_aliases(
    annotation: str, expected_children: bool
):
    """The slot aliases are part of the parser's own vocabulary, so a header
    needs no import path to name them."""
    from typing import get_args

    from pyjinhx._component import PjxSlot

    fields = parse_props_header(f"{{#def value: {annotation} #}}")
    assert fields is not None
    name, resolved, default = fields[0]
    assert (name, default) == ("value", ...)
    marker = next(m for m in get_args(resolved) if isinstance(m, PjxSlot))
    assert marker.children is expected_children


def test_slot_names_resolve_to_the_component_module_aliases_themselves():
    """Same object as the Python-class API uses, so every consumer that already
    reads PjxSlot metadata keeps working with no translation layer."""
    from pyjinhx._component import Children, Slot

    assert parse_props_header("{#def value: Slot #}") == [("value", Slot, ...)]
    assert parse_props_header("{#def content: Children #}") == [
        ("content", Children, ...)
    ]


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


def test_a_plain_jinja_comment_is_not_a_header():
    assert parse_props_header("{# just a comment #}<div></div>") is None


def test_parsing_uses_only_the_stdlib():
    """Parsing must stay usable without the component spine loaded; only the
    generation half of this module may reach for pydantic."""
    import ast as ast_module
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "pyjinhx" / "props_header.py"
    tree = ast_module.parse(source.read_text(encoding="utf-8"))
    parse_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast_module.FunctionDef)
        and node.name == "parse_props_header"
    )
    names = {
        node.id
        for node in ast_module.walk(parse_fn)
        if isinstance(node, ast_module.Name)
    }
    assert "create_model" not in names
    assert "_OpenComponent" not in names


def test_a_css_block_above_the_header_does_not_hide_it():
    source = "{#css\n.card { padding: 1rem; }\n#}\n{#def title: str #}\n<div></div>"

    assert parse_props_header(source) == [("title", str, ...)]


def test_the_header_is_found_in_the_middle_and_at_the_end():
    middle = "<p></p>\n{#def title: str #}\n<div></div>"
    end = "<div></div>\n{#def title: str #}"

    assert parse_props_header(middle) == [("title", str, ...)]
    assert parse_props_header(end) == [("title", str, ...)]


def test_a_second_header_raises_at_its_line():
    source = "{#def a #}\n<div></div>\n{#def b #}"

    with pytest.raises(TemplateSyntaxError) as raised:
        parse_props_header(source)

    assert raised.value.lineno == 3


def test_the_spaced_legacy_header_still_parses_in_first_position():
    assert parse_props_header("{# def title: str #}<div></div>") == [
        ("title", str, ...)
    ]


def test_the_spaced_form_anywhere_else_is_prose():
    assert parse_props_header("<div></div>\n{# def title: str #}") is None
    assert parse_props_header("{#css\n.a {}\n#}\n{# def title: str #}") is None


def test_literal_annotation_becomes_a_typing_literal():
    from typing import Literal

    assert parse_props_header('{#def tone: Literal["info", "warn"] = "info" #}') == [
        ("tone", Literal["info", "warn"], "info")
    ]


def test_literal_members_must_be_literals():
    with pytest.raises(ValueError, match="tone"):
        parse_props_header("{#def tone: Literal[SOME_NAME] #}")


@pytest.mark.parametrize(
    "annotation, expected",
    [
        ("list[str]", list[str]),
        ("dict[str, int]", dict[str, int]),
        ("list[list[int]]", list[list[int]]),
    ],
)
def test_generic_annotations_resolve_their_arguments(annotation: str, expected: Any):
    assert parse_props_header(f"{{#def value: {annotation} #}}") == [
        ("value", expected, ...)
    ]


def test_list_of_slot_keeps_the_slot_alias_as_its_argument():
    from pyjinhx._component import Slot

    assert parse_props_header("{#def rows: list[Slot] #}") == [
        ("rows", list[Slot], ...)
    ]


def test_union_of_two_types_is_a_real_union():
    assert parse_props_header("{#def size: str | int #}") == [("size", str | int, ...)]


def test_attribute_types_resolve_to_pyjinhx_types():
    from pyjinhx._component import AttrValue, ExtraAttrs

    assert parse_props_header("{#def attrs: ExtraAttrs, title: AttrValue #}") == [
        ("attrs", ExtraAttrs, ...),
        ("title", AttrValue, ...),
    ]


@pytest.mark.parametrize(
    "default",
    ["DEFAULT_X", "make()", "app.make(1)", "app.make(n=1)", "app.B * 2", "lambda: 1"],
    ids=["bare-name", "bare-call", "call-args", "call-kwargs", "expression", "lambda"],
)
def test_a_default_outside_the_three_forms_says_what_is_allowed(default: str):
    """A bare name is refused, not guessed at: a typo must never become an import."""
    with pytest.raises(ValueError) as excinfo:
        parse_props_header(f"{{#def x: int = {default} #}}")
    message = str(excinfo.value)
    assert "default for 'x'" in message
    assert "a literal" in message
    assert "a dotted name (pkg.mod.NAME)" in message
    assert "a dotted name called with no arguments (pkg.mod.make())" in message


def test_parsing_a_dotted_default_imports_nothing():
    module = "tests.pyjinhx.header_import_probe"
    sys.modules.pop(module, None)
    parse_props_header(
        f"{{#def tone: str = {module}.Probe.ON, at: str = {module}.f() #}}"
    )
    assert module not in sys.modules
