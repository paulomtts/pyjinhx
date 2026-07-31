"""Unit tests for building a component class from a parsed {#def #} header.

Generation only: warning on stale headers (#377), the component() factory
(#378), and discovery's filename -> tag derivation are separate surfaces.
"""

from typing import Any

import pytest

from pyjinhx2.component import BaseComponent, OpenComponent
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.props_header import build_component_class, parse_props_header


def test_generated_class_subclasses_the_open_model_base():
    """ADR 0006: classless components need pass-through attributes, so they
    must never hang off the strict core directly."""
    cls = build_component_class([("title", str, ...)], "Card")
    assert issubclass(cls, OpenComponent)
    assert issubclass(cls, BaseComponent)
    assert cls.__name__ == "Card"


def test_generated_class_carries_field_types_and_defaults():
    fields = [("title", str, ...), ("count", int, 3), ("flag", bool | None, None)]
    cls = build_component_class(fields, "Card")

    assert cls.model_fields["title"].annotation is str
    assert cls.model_fields["title"].is_required()
    assert cls.model_fields["count"].annotation is int
    assert cls.model_fields["count"].default == 3
    assert cls.model_fields["flag"].default is None


def test_generated_class_instantiates_with_and_without_optional_props():
    fields = [("title", str, ...), ("count", int, 3), ("flag", bool | None, None)]
    cls = build_component_class(fields, "Card")

    # cls is a dynamically generated pydantic model; basedpyright cannot see
    # its header-declared fields statically, unlike a hand-authored class.
    minimal = cls(title="hi")  # pyright: ignore[reportCallIssue]
    assert (minimal.title, minimal.count, minimal.flag) == (  # pyright: ignore[reportAttributeAccessIssue]
        "hi",
        3,
        None,
    )

    full = cls(title="hi", count=7, flag=True)  # pyright: ignore[reportCallIssue]
    assert (full.title, full.count, full.flag) == (  # pyright: ignore[reportAttributeAccessIssue]
        "hi",
        7,
        True,
    )


def test_missing_required_prop_still_fails_validation():
    """Open extras must not soften a required declared prop into optional."""
    cls = build_component_class([("title", str, ...)], "Card")
    with pytest.raises(ValueError):
        cls()


def test_generated_class_is_marked_classless():
    """#377 and #378 branch on provenance; the marker is the only signal that a
    class came from a header rather than from hand-written Python."""
    cls = build_component_class([("title", str, ...)], "Card")
    assert cls._pjx_classless is True  # pyright: ignore[reportAttributeAccessIssue]


def test_generated_class_accepts_undeclared_attributes():
    """Sanity check that create_model did not re-close the open model."""
    cls = build_component_class([("title", str, ...)], "Card")
    instance = cls(title="hi", data_role="banner")  # pyright: ignore[reportCallIssue]
    assert instance.model_extra == {"data_role": "banner"}


def test_empty_field_list_generates_a_usable_class():
    """An empty header still declares the template classless, with zero props."""
    cls = build_component_class([], "Card")
    assert issubclass(cls, OpenComponent)
    assert set(cls.model_fields) == set(OpenComponent.model_fields)
    assert cls().model_extra == {}


def test_generated_class_gets_a_frozen_class_descriptor():
    """Invariant 5: per-class facts are resolved once, when the class is built,
    not on every render. create_model must not bypass that hook."""
    cls = build_component_class([("title", str, ...)], "Card")
    descriptor = cls.__pjx_descriptor__
    assert isinstance(descriptor, ClassDescriptor)
    # The MRO walk probes Card's own candidate (not found, since Card has no
    # file of its own yet) and falls back unprobed to OpenComponent's, per
    # `_walk_template`'s documented last-ancestor-unprobed semantics.
    assert descriptor.template_path.name == "open_component.pjx"


@pytest.mark.parametrize(
    "annotation",
    [str, int, float, bool, list, dict, Any, str | None],
    ids=["str", "int", "float", "bool", "list", "dict", "Any", "optional"],
)
def test_every_header_type_passes_through_unchanged(annotation: Any):
    """The parser owns the type vocabulary; generation must not remap it."""
    cls = build_component_class([("prop", annotation, ...)], "Card")
    assert cls.model_fields["prop"].annotation == annotation


def test_parse_and_build_compose_end_to_end():
    fields = parse_props_header('{#def title: str, variant: str = "primary" #}')
    assert fields is not None
    cls = build_component_class(fields, "Card")
    assert cls(title="hi").variant == "primary"  # pyright: ignore[reportCallIssue,reportAttributeAccessIssue]
