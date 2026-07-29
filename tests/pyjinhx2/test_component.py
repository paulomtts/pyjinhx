import ast
import inspect

import pytest
from pydantic import BaseModel, Field, ValidationError

import pyjinhx2.component
from pyjinhx2.component import BaseComponent


class Address(BaseModel):
    city: str


class Card(BaseComponent):
    name: str
    count: int = 0
    tags: list[str] = Field(default_factory=list)
    address: Address | None = None


class Panel(BaseComponent):
    title: str = ""


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
