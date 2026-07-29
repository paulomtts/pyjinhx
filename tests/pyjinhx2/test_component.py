import ast
import inspect

import pytest
from pydantic import BaseModel, Field, ValidationError

import pyjinhx2.component
from pyjinhx2.component import BaseComponent, Slot


class Address(BaseModel):
    city: str


class Card(BaseComponent):
    name: str
    count: int = 0
    tags: list[str] = Field(default_factory=list)
    address: Address | None = None


class Panel(BaseComponent):
    title: str = ""


class Named(BaseComponent):
    auto_id = False


class Structural(BaseComponent):
    sources: list = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    typed_items: list[str] = Field(default_factory=list)
    typed_map: dict[str, int] = Field(default_factory=dict)
    address: Address | None = None
    maybe_items: list[str] | None = None
    label: str | list = ""


class Slotted(BaseComponent):
    body: Slot = ""


class StrictStructural(BaseComponent):
    auto_id = False
    sources: list = Field(default_factory=list)


class TestStrictConfig:
    def test_forbids_extra_fields(self):
        assert BaseComponent.model_config.get("extra") == "forbid"

    def test_declares_only_the_id_field(self):
        assert set(BaseComponent.model_fields) == {"id"}

    def test_bare_base_instantiates(self):
        assert BaseComponent() is not None

    def test_bare_base_rejects_any_kwarg(self):
        with pytest.raises(ValidationError):
            BaseComponent(name="x")  # pyright: ignore[reportCallIssue]


class TestSubclassing:
    def test_accepts_declared_fields(self):
        card = Card(name="x", count=2, tags=["a"], address=Address(city="Lisbon"))
        assert card.name == "x"
        assert card.count == 2
        assert card.tags == ["a"]
        assert card.address == Address(city="Lisbon")

    def test_applies_declared_defaults(self):
        card = Card(name="x")
        assert card.count == 0
        assert card.tags == []
        assert card.address is None

    def test_rejects_undeclared_kwarg(self):
        with pytest.raises(ValidationError):
            Card(name="x", extra_field=1)  # pyright: ignore[reportCallIssue]

    def test_still_validates_declared_field_types(self):
        with pytest.raises(ValidationError):
            Card(name="x", count="not-an-int")  # pyright: ignore[reportArgumentType]


class TestAutoId:
    def test_omitting_id_auto_generates_pjx_prefixed_id(self):
        first = Card(name="a")
        second = Card(name="b")
        assert first.id.startswith("pjx-")
        assert second.id.startswith("pjx-")
        assert first.id != second.id

    def test_auto_generated_ids_are_monotonic_and_unique_across_subclasses(self):
        ids = [Card(name="a").id, Panel().id, Card(name="b").id, Panel().id]
        suffixes = [int(component_id.removeprefix("pjx-")) for component_id in ids]
        assert suffixes == sorted(suffixes)
        assert len(set(suffixes)) == len(suffixes)

    def test_explicit_id_is_used_as_given(self):
        assert Card(name="a", id="custom-id").id == "custom-id"

    def test_empty_string_id_falls_back_to_auto_id(self):
        assert Card(name="a", id="").id.startswith("pjx-")

    def test_none_id_falls_back_to_auto_id(self):
        assert Card(name="a", id=None).id.startswith("pjx-")  # pyright: ignore[reportArgumentType]


class TestAutoIdOptOut:
    def test_auto_id_false_without_explicit_id_raises(self):
        with pytest.raises(ValidationError):
            Named()

    def test_auto_id_false_with_falsy_id_raises(self):
        with pytest.raises(ValidationError):
            Named(id="")

    def test_auto_id_false_with_explicit_id_succeeds(self):
        assert Named(id="x").id == "x"

    def test_auto_id_defaults_to_on(self):
        assert BaseComponent.auto_id is True
        assert Card(name="a").id.startswith("pjx-")

    def test_auto_id_is_not_a_model_field(self):
        assert "auto_id" not in BaseComponent.model_fields
        assert "auto_id" not in Named.model_fields


class TestJsonCoercion:
    def test_json_string_coerces_to_list(self):
        assert Structural(
            typed_items='["a", "b"]'  # pyright: ignore[reportArgumentType]
        ).typed_items == ["a", "b"]

    def test_json_string_coerces_to_dict(self):
        assert Structural(
            typed_map='{"a": 1}'  # pyright: ignore[reportArgumentType]
        ).typed_map == {"a": 1}

    def test_json_object_string_coerces_to_base_model_field(self):
        assert Structural(
            address='{"city": "Lisbon"}'  # pyright: ignore[reportArgumentType]
        ).address == Address(city="Lisbon")

    def test_optional_annotation_still_coerces(self):
        assert Structural(
            maybe_items='["a"]'  # pyright: ignore[reportArgumentType]
        ).maybe_items == ["a"]


FORBIDDEN_IMPORTS = (
    "pyjinhx2.render",
    "pyjinhx2.descriptor",
    "pyjinhx2.session",
    "pyjinhx2.reactive",
    "pyjinhx",
)


def test_component_module_does_not_import_above_itself():
    """component.py sits below descriptor/render in the import graph, so it must
    not reach up into them (nor into session.py, reactive/, or v0.x pyjinhx)."""
    tree = ast.parse(inspect.getsource(pyjinhx2.component))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "component.py must not use relative imports"
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert name not in FORBIDDEN_IMPORTS, f"component.py must not import {name}"
            assert not any(name.startswith(f"{f}.") for f in FORBIDDEN_IMPORTS), (
                f"component.py must not import {name}"
            )
