import ast
import inspect

import pytest
from pydantic import BaseModel, ValidationError

import pyjinhx2.component
from pyjinhx2.component import BaseComponent


class Address(BaseModel):
    city: str


class Card(BaseComponent):
    name: str
    count: int = 0
    tags: list[str] = []
    address: Address | None = None


class TestStrictConfig:
    def test_forbids_extra_fields(self):
        assert BaseComponent.model_config.get("extra") == "forbid"

    def test_declares_no_fields_of_its_own(self):
        assert BaseComponent.model_fields == {}

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
            assert name not in FORBIDDEN_IMPORTS, (
                f"component.py must not import {name}"
            )
            assert not any(name.startswith(f"{f}.") for f in FORBIDDEN_IMPORTS), (
                f"component.py must not import {name}"
            )
