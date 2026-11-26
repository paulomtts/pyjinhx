"""Unit tests for building a component class from a parsed {#def #} header.

Generation only: warning on stale headers (#377), the component() factory
(#378), and discovery's filename -> tag derivation are separate surfaces.
"""

import datetime
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from pyjinhx.components.base import BaseComponent, ClassDescriptor, _OpenComponent
from pyjinhx.components.props_header import build_component_class, parse_props_header
from tests.pyjinhx import header_names


def test_generated_class_subclasses_the_open_model_base():
    """ADR 0006: classless components need pass-through attributes, so they
    must never hang off the strict core directly."""
    cls = build_component_class([("title", str, ...)], "Card")
    assert issubclass(cls, _OpenComponent)
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
    assert issubclass(cls, _OpenComponent)
    assert set(cls.model_fields) == set(_OpenComponent.model_fields)
    assert cls().model_extra == {}


def test_generated_class_gets_a_frozen_class_descriptor():
    """Invariant 5: per-class facts are resolved once, when the class is built,
    not on every render. create_model must not bypass that hook."""
    cls = build_component_class([("title", str, ...)], "Card")
    descriptor = cls.__pjx_descriptor__
    assert isinstance(descriptor, ClassDescriptor)
    # The MRO walk probes Card's own candidate (not found, since Card has no
    # file of its own yet) and falls back unprobed to _OpenComponent's, per
    # `_walk_template`'s documented last-ancestor-unprobed semantics.
    assert descriptor.template_path.name == "_open_component.pjx"


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


@pytest.mark.parametrize(
    "annotation, prop",
    [("Slot", "value"), ("Children", "content")],
    ids=["slot", "children"],
)
def test_header_declared_slots_are_detected_as_slots_on_the_built_class(
    annotation: str, prop: str
):
    """Closing the loop: resolution is only useful if the marker survives
    create_model and the shared slot check sees it."""
    from pyjinhx.components.base import _is_slot_field

    fields = parse_props_header(f"{{#def {prop}: {annotation} #}}")
    assert fields is not None
    cls = build_component_class(fields, "Card")
    assert _is_slot_field(cls, prop) is True


def test_header_declared_plain_props_are_not_slots():
    """The detection above must come from the marker, not from being generated."""
    from pyjinhx.components.base import _is_slot_field

    fields = parse_props_header("{#def title: str #}")
    assert fields is not None
    cls = build_component_class(fields, "Card")
    assert _is_slot_field(cls, "title") is False


def test_descriptor_template_path_is_provisional_until_relocated(tmp_path, monkeypatch):
    """A generated class has no module file of its own, so its first descriptor
    resolves against this package's directory (``_OpenComponent``'s own template
    candidate, since ``Card`` has none there and the walk's unprobed fallback is
    the nearest ancestor that does have a defining module). Discovery must
    re-point ``__module__`` at the template's real package and rebuild before
    the path means anything — proven here by only then getting a real template
    file on disk to resolve to."""
    import sys
    import types
    from pathlib import Path

    import pyjinhx.components.props_header as props_header_module
    from pyjinhx.components.base import rebuild_class_descriptor

    cls = build_component_class([("title", str, ...)], "Card")
    assert cls.__module__ == props_header_module.__name__
    assert cls.__pjx_descriptor__.template_path == (
        Path(props_header_module.__file__).parent / "_open_component.pjx"
    )

    # Simulate discovery relocating the class beside its real template: a
    # throwaway module whose __file__ lives next to an actual card.pjx.
    (tmp_path / "card.pjx").write_text("<div></div>")
    fake_module = types.ModuleType("pjx_generated.card_module")
    fake_module.__file__ = str(tmp_path / "__init__.py")
    monkeypatch.setitem(sys.modules, fake_module.__name__, fake_module)

    cls.__module__ = fake_module.__name__
    rebuild_class_descriptor(cls)
    assert cls.__pjx_descriptor__.template_path == tmp_path / "card.pjx"


@pytest.mark.parametrize(
    "annotation",
    ["Slot | None", "Optional[Slot]"],
    ids=["union", "optional"],
)
def test_header_declared_slot_union_is_detected_as_slot_on_the_built_class(
    annotation: str,
):
    """Pydantic hoists metadata only from the outermost Annotated, so an
    optional slot arrives with empty field metadata and the marker still nested
    inside the union; detection has to unwrap it."""
    from pyjinhx.components.base import _is_slot_field

    fields = parse_props_header(f"{{#def value: {annotation} #}}")
    assert fields is not None
    cls = build_component_class(fields, "Card")
    assert _is_slot_field(cls, "value") is True


def _build(header: str):
    fields = parse_props_header(header)
    assert fields is not None
    return build_component_class(fields, "Card")


def test_literal_prop_rejects_a_value_outside_its_members():
    from pydantic import ValidationError

    cls = _build('{#def tone: Literal["info", "warn"] = "info" #}')
    assert cls(tone="warn").tone == "warn"  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]
    with pytest.raises(ValidationError):
        cls(tone="bad")  # pyright: ignore[reportCallIssue]


def test_union_prop_accepts_either_member_and_rejects_others():
    from pydantic import ValidationError

    cls = _build("{#def size: str | int = 1 #}")
    assert cls(size="x").size == "x"  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]
    assert cls(size=2).size == 2  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]
    with pytest.raises(ValidationError):
        cls(size=[])  # pyright: ignore[reportCallIssue]


def test_extra_attrs_prop_validates_attribute_names():
    from pydantic import ValidationError

    cls = _build("{#def attrs: ExtraAttrs = {} #}")
    assert cls(attrs={"data-x": "y"}).attrs == {"data-x": "y"}  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]
    with pytest.raises(ValidationError):
        cls(attrs={'a"b': "x"})  # pyright: ignore[reportCallIssue]


def test_mutable_defaults_are_not_shared_between_instances():
    cls = _build("{#def items: list = [], opts: dict = {} #}")
    first, second = cls(), cls()  # pyright: ignore[reportCallIssue]
    first.items.append(1)  # pyright: ignore[reportAttributeAccessIssue]
    first.opts["a"] = 1  # pyright: ignore[reportAttributeAccessIssue]
    assert second.items == []  # pyright: ignore[reportAttributeAccessIssue]
    assert second.opts == {}  # pyright: ignore[reportAttributeAccessIssue]


def test_required_id_turns_off_auto_id():
    cls = _build("{#def id: str, title: str #}")
    assert cls.auto_id is False
    assert cls(id="x", title="t").id == "x"  # pyright: ignore[reportCallIssue]
    with pytest.raises(ValueError, match="id is required"):
        cls(title="t")  # pyright: ignore[reportCallIssue]
    assert list(cls.model_fields).count("id") == 1


def test_header_without_id_still_auto_generates_ids():
    cls = _build("{#def title: str #}")
    assert cls.auto_id is True
    assert cls(title="t").id.startswith("pjx-")  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize("header", ["{#def id: int #}", '{#def id: str = "fixed" #}'])
def test_id_may_only_be_a_required_str(header: str):
    with pytest.raises(ValueError, match="id.*required.*str"):
        _build(header)


@pytest.mark.parametrize(
    "annotation, expected",
    [
        ("datetime.datetime", datetime.datetime),
        ("tests.pyjinhx.header_names.Tone", header_names.Tone),
        ("list[uuid.UUID]", list[uuid.UUID]),
        ("tuple[uuid.UUID, ...]", tuple[uuid.UUID, ...]),
        ("uuid.UUID | None", uuid.UUID | None),
    ],
)
def test_dotted_annotation_resolves_by_import(annotation: str, expected: Any):
    cls = _build(f"{{#def value: {annotation} #}}")
    assert cls.model_fields["value"].annotation == expected


def test_dotted_enum_annotation_coerces_its_value():
    cls = _build("{#def tone: tests.pyjinhx.header_names.Tone #}")
    instance = cls(tone="warn")  # pyright: ignore[reportCallIssue]
    assert instance.tone is header_names.Tone.WARN  # pyright: ignore[reportAttributeAccessIssue]


def test_dotted_names_import_when_the_class_is_built_not_when_parsed():
    """Parsing runs at registration, for every template, while the app's own
    modules may still be importing; an import there could find one half-built."""
    module = "tests.pyjinhx.header_import_probe"
    sys.modules.pop(module, None)
    fields = parse_props_header(f"{{#def value: {module}.Probe | None #}}")
    assert module not in sys.modules

    assert fields is not None
    build_component_class(fields, "Card")
    assert module in sys.modules


def test_dotted_default_is_the_named_constant():
    cls = _build("{#def size: int = tests.pyjinhx.header_names.PAGE_SIZE #}")
    assert cls.model_fields["size"].default == header_names.PAGE_SIZE


def test_dotted_default_may_be_an_enum_member():
    cls = _build(
        "{#def tone: tests.pyjinhx.header_names.Tone"
        " = tests.pyjinhx.header_names.Tone.INFO #}"
    )
    assert cls().tone is header_names.Tone.INFO  # pyright: ignore[reportAttributeAccessIssue]


def test_dotted_call_default_is_a_per_instance_factory():
    cls = _build("{#def at: datetime.datetime = datetime.datetime.now() #}")
    assert cls.model_fields["at"].default_factory == datetime.datetime.now
    first = cls().at  # pyright: ignore[reportAttributeAccessIssue]
    time.sleep(0.001)
    assert cls().at > first  # pyright: ignore[reportAttributeAccessIssue]


def test_dotted_factory_result_is_not_shared_between_instances():
    cls = _build("{#def tags: list = tests.pyjinhx.header_names.make_tags() #}")
    first, second = cls(), cls()
    assert first.tags == ["new"]  # pyright: ignore[reportAttributeAccessIssue]
    assert first.tags is not second.tags  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "header, path, cause",
    [
        ("{#def tone: no_such_pkg.Tone #}", "no_such_pkg.Tone", ImportError),
        (
            "{#def size: int = tests.pyjinhx.header_names.NOPE #}",
            "tests.pyjinhx.header_names.NOPE",
            AttributeError,
        ),
        (
            "{#def tags: list = no_such_pkg.make() #}",
            "no_such_pkg.make",
            ImportError,
        ),
    ],
    ids=["type", "constant", "factory"],
)
def test_a_dotted_name_that_does_not_import_names_the_prop_and_the_path(
    header: str, path: str, cause: type[Exception]
):
    fields = parse_props_header(header)
    assert fields is not None
    with pytest.raises(ValueError, match=re.escape(repr(path))) as excinfo:
        build_component_class(fields, "Card", Path("ui/card.pjx"))
    message = str(excinfo.value)
    assert message.startswith("<Card> (ui/card.pjx):")
    assert repr(fields[0][0]) in message
    assert isinstance(excinfo.value.__cause__, cause)


def test_a_dotted_factory_that_is_not_callable_is_rejected_at_build():
    """Caught here rather than as a TypeError on the first render."""
    fields = parse_props_header(
        "{#def size: int = tests.pyjinhx.header_names.PAGE_SIZE() #}"
    )
    assert fields is not None
    with pytest.raises(ValueError, match="'size'.*not callable"):
        build_component_class(fields, "Card")
