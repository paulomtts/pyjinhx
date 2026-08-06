import ast
import inspect
from typing import ClassVar

import pytest
from pydantic import BaseModel, Field, ValidationError
from pydantic.errors import PydanticUserError

import pyjinhx._component
from pyjinhx._component import (
    AttrValue,
    BaseComponent,
    Children,
    ExtraAttrs,
    Slot,
    _OpenComponent,
    validate_attr_value,
    validate_extra_attrs,
)


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
    owner: Address = Field(default_factory=lambda: Address(city="unset"))
    maybe_items: list[str] | None = None
    maybe_map: dict[str, int] | None = None
    label: str | list = ""
    either: list | dict = Field(default_factory=list)


class Slotted(BaseComponent):
    body: Slot = ""


class CachedListHolder(BaseComponent):
    data: list[str] = Field(default_factory=list)


class StrictStructural(BaseComponent):
    auto_id = False
    sources: list = Field(default_factory=list)
    count: int = 0
    meta: dict = Field(default_factory=dict)
    address: Address | None = None


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

    def test_declared_defaults_apply_under_auto_id_opt_out(self):
        # _require_explicit_id is a mode="before" validator; it must gate the id
        # without disturbing default application for any field kind.
        component = StrictStructural(id="fixed")
        assert component.id == "fixed"
        assert component.sources == []
        assert component.count == 0
        assert component.meta == {}
        assert component.address is None

    def test_defaults_do_not_satisfy_the_required_id(self):
        # Every other field defaults, so a bare construction must still fail on
        # the id alone — defaults never stand in for the explicit id.
        with pytest.raises(ValidationError) as excinfo:
            StrictStructural()
        assert "auto_id = False" in str(excinfo.value)
        assert "StrictStructural" in str(excinfo.value)


class TestJsonCoercion:
    def test_json_string_coerces_to_list(self):
        assert Structural(
            typed_items='["a", "b"]'  # pyright: ignore[reportArgumentType]
        ).typed_items == ["a", "b"]

    def test_json_string_coerces_to_dict(self):
        assert Structural(
            typed_map='{"a": 1}'  # pyright: ignore[reportArgumentType]
        ).typed_map == {"a": 1}

    def test_json_object_string_coerces_to_optional_base_model_field(self):
        assert Structural(
            address='{"city": "Lisbon"}'  # pyright: ignore[reportArgumentType]
        ).address == Address(city="Lisbon")

    def test_optional_annotation_still_coerces(self):
        assert Structural(
            maybe_items='["a"]'  # pyright: ignore[reportArgumentType]
        ).maybe_items == ["a"]

    def test_union_with_str_is_not_coerced(self):
        assert Structural(label="[1, 2, 3]").label == "[1, 2, 3]"

    def test_slot_field_is_never_coerced(self):
        assert Slotted(body='{"not": "json-here"}').body == '{"not": "json-here"}'

    def test_children_slot_field_is_never_coerced(self):
        class WithChildren(BaseComponent):
            content: Children = ""

        assert WithChildren(content="[1, 2]").content == "[1, 2]"

    def test_invalid_json_raises_validation_error_naming_class_and_field(self):
        with pytest.raises(ValidationError) as excinfo:
            Structural(sources="[not json")  # pyright: ignore[reportArgumentType]
        message = str(excinfo.value)
        assert "Structural" in message
        assert "sources" in message

    def test_non_json_looking_string_is_left_for_pydantic_to_reject(self):
        with pytest.raises(ValidationError) as excinfo:
            Structural(sources="plain text")  # pyright: ignore[reportArgumentType]
        assert "invalid JSON attribute value" not in str(excinfo.value)

    def test_empty_string_is_left_for_pydantic_to_reject(self):
        with pytest.raises(ValidationError) as excinfo:
            Structural(meta="")  # pyright: ignore[reportArgumentType]
        assert "invalid JSON attribute value" not in str(excinfo.value)

    def test_real_values_pass_through_untouched(self):
        address = Address(city="Porto")
        component = Structural(
            sources=[1, 2], meta={"a": 1}, typed_items=["x"], address=address
        )
        assert component.sources == [1, 2]
        assert component.meta == {"a": 1}
        assert component.typed_items == ["x"]
        assert component.address == address

    def test_non_dict_input_is_passed_through(self):
        assert Structural.model_validate(Structural(typed_items=["a"])).typed_items == [
            "a"
        ]

    def test_coercion_does_not_disturb_auto_id_opt_out(self):
        with pytest.raises(ValidationError):
            StrictStructural(sources='["a"]')  # pyright: ignore[reportArgumentType]
        component = StrictStructural(
            id="fixed",
            sources='["a"]',  # pyright: ignore[reportArgumentType]
        )
        assert component.id == "fixed"
        assert component.sources == ["a"]

    def test_coercion_does_not_disturb_auto_id_generation(self):
        assert Structural(
            typed_items='["a"]'  # pyright: ignore[reportArgumentType]
        ).id.startswith("pjx-")

    def test_json_string_coerces_to_bare_list(self):
        assert Structural(
            sources="[1, 2]"  # pyright: ignore[reportArgumentType]
        ).sources == [1, 2]

    def test_json_string_coerces_to_bare_dict(self):
        assert Structural(
            meta='{"a": 1}'  # pyright: ignore[reportArgumentType]
        ).meta == {"a": 1}

    def test_json_string_coerces_to_non_optional_base_model_field(self):
        # The plain-BaseModel cell: no `| None` to strip, so the union branch of
        # _is_json_coercible_annotation is skipped entirely.
        assert Structural(
            owner='{"city": "Lisbon"}'  # pyright: ignore[reportArgumentType]
        ).owner == Address(city="Lisbon")

    def test_optional_dict_annotation_still_coerces(self):
        assert Structural(
            maybe_map='{"a": 1}'  # pyright: ignore[reportArgumentType]
        ).maybe_map == {"a": 1}

    def test_two_arg_non_none_union_is_not_coerced(self):
        # `list | dict` keeps two non-None members, so the len(args) != 1 branch
        # bails out and the JSON-looking string reaches Pydantic as a raw str.
        with pytest.raises(ValidationError) as excinfo:
            Structural(either="[1, 2]")  # pyright: ignore[reportArgumentType]
        error_types = {error["type"] for error in excinfo.value.errors()}
        assert error_types == {"list_type", "dict_type"}
        assert "invalid JSON attribute value" not in str(excinfo.value)

    @pytest.mark.parametrize(
        ("field_name", "error_type"),
        [
            ("sources", "list_type"),
            ("meta", "dict_type"),
            ("owner", "model_type"),
            ("maybe_map", "dict_type"),
        ],
    )
    def test_non_string_bad_type_on_coercible_field_still_raises_validation_error(
        self, field_name, error_type
    ):
        # _coerce_json_string_attrs skips non-str values outright, so Pydantic's
        # own type check must still fire — the bypass must not swallow it.
        with pytest.raises(ValidationError) as excinfo:
            Structural(**{field_name: 123})  # pyright: ignore[reportArgumentType]
        assert [error["type"] for error in excinfo.value.errors()] == [error_type]
        assert "invalid JSON attribute value" not in str(excinfo.value)


class TestJsonCoercibleFieldsCache:
    def test_json_coercion_consistent_across_instances(self):
        # The coercibility verdict is resolved once per class; repeated
        # construction must keep producing the same coerced value as a
        # directly-constructed Python value would.
        instances = [
            CachedListHolder(data='["a", "b"]')  # pyright: ignore[reportArgumentType]
            for _ in range(3)
        ]
        assert [instance.data for instance in instances] == [["a", "b"]] * 3
        assert instances[0].data == CachedListHolder(data=["a", "b"]).data


class Anchor(BaseComponent):
    href: AttrValue = ""


class Tagged(BaseComponent):
    attrs: ExtraAttrs = Field(default_factory=dict)


class TestValidateAttrValue:
    def test_rejects_double_quote(self):
        with pytest.raises(ValueError):
            validate_attr_value('has "quote')

    def test_accepts_single_quote_alone(self):
        assert validate_attr_value("it's fine") == "it's fine"

    def test_returns_plain_value_unchanged(self):
        assert validate_attr_value("safe") == "safe"


class TestValidateExtraAttrs:
    def test_accepts_plain_name(self):
        value = {"data-foo": "bar"}
        assert validate_extra_attrs(value) == value

    @pytest.mark.parametrize("name", ["@click", ":bind", "data-x", "x:y", "hx-get"])
    def test_accepts_valid_names(self, name):
        assert validate_extra_attrs({name: "v"}) == {name: "v"}

    @pytest.mark.parametrize("name", ["1bad", "", "-lead", "has space", "a<b"])
    def test_rejects_invalid_names(self, name):
        with pytest.raises(ValueError):
            validate_extra_attrs({name: "v"})

    def test_rejects_value_with_both_quote_types(self):
        with pytest.raises(ValueError):
            validate_extra_attrs({"data-x": 'it\'s "bad"'})

    def test_accepts_value_with_only_double_quotes(self):
        value = {"data-x": 'say "hi"'}
        assert validate_extra_attrs(value) == value

    def test_accepts_value_with_only_single_quotes(self):
        value = {"data-x": "it's fine"}
        assert validate_extra_attrs(value) == value


class TestQuoteSafeFieldTypes:
    def test_attr_value_field_rejects_double_quote_at_construction(self):
        with pytest.raises(ValidationError):
            Anchor(href='/a?x="y"')

    def test_attr_value_field_accepts_safe_value(self):
        assert Anchor(href="/a?x=y").href == "/a?x=y"

    def test_extra_attrs_field_rejects_bad_name_at_construction(self):
        with pytest.raises(ValidationError):
            Tagged(attrs={"1bad": "x"})

    def test_extra_attrs_field_rejects_bad_value_at_construction(self):
        with pytest.raises(ValidationError):
            Tagged(attrs={"data-x": 'it\'s "bad"'})

    def test_extra_attrs_field_accepts_valid_mapping(self):
        assert Tagged(attrs={"@click": "go()"}).attrs == {"@click": "go()"}


class TestReservedNameCollisions:
    def test_auto_id_as_real_field_raises_at_class_definition(self):
        with pytest.raises(TypeError) as excinfo:

            class Bad(BaseComponent):
                auto_id: bool = False  # pyright: ignore[reportIncompatibleVariableOverride]

        message = str(excinfo.value)
        assert "Bad" in message
        assert "auto_id" in message
        assert "ClassVar" in message

    def test_auto_id_as_classvar_is_allowed(self):
        class Good(BaseComponent):
            auto_id: ClassVar[bool] = False

        assert "auto_id" not in Good.model_fields
        with pytest.raises(ValidationError):
            Good()
        assert Good(id="x").id == "x"

    def test_bare_auto_id_assignment_is_still_allowed(self):
        class Bare(BaseComponent):
            auto_id = False

        assert "auto_id" not in Bare.model_fields
        assert Bare(id="x").id == "x"

    def test_plain_subclass_is_unaffected(self):
        class Plain(BaseComponent):
            name: str = ""

        assert Plain(name="a").id.startswith("pjx-")

    def test_id_retyped_to_non_str_raises_at_class_definition(self):
        with pytest.raises(TypeError) as excinfo:

            class BadId(BaseComponent):
                id: int = 0  # pyright: ignore[reportIncompatibleVariableOverride]

        message = str(excinfo.value)
        assert "BadId" in message
        assert "id" in message
        assert "str" in message

    def test_id_as_classvar_raises_at_class_definition(self):
        # pydantic itself rejects this first (the inherited `_validate_id`
        # decorator no longer matches a field), so accept either error type —
        # what matters is that it blows up at class-definition time.
        with pytest.raises((TypeError, PydanticUserError)):

            class ClassVarId(BaseComponent):
                id: ClassVar[str] = "x"  # pyright: ignore[reportIncompatibleVariableOverride]

    def test_id_default_and_metadata_may_be_overridden(self):
        class FixedId(BaseComponent):
            id: str = Field(default="fixed", description="a fixed id")

        assert FixedId().id == "fixed"
        assert FixedId(id="custom").id == "custom"
        # the inherited _validate_id lineage still applies
        assert FixedId(id="").id.startswith("pjx-")


FORBIDDEN_IMPORTS = ("pyjinhx.reactive",)


def test_component_module_does_not_import_above_itself():
    """_component.py sits below descriptor/render in the import graph, so it must
    not reach up into them (nor into reactive/) — except the two
    sanctioned edges: importing ``ClassDescriptor`` from descriptor.py (#271) to
    build and attach it in ``__pydantic_init_subclass__``, and the local,
    method-body-only imports of render.py/session.py inside
    ``BaseComponent.render()`` (#643), which exist because render.py imports
    BaseComponent at module scope and a module-level edge back would be a real
    cycle. tests/pyjinhx/test_import_graph.py is the whole-package view that
    enforces _component.py is the *only* module allowed those edges."""
    tree = ast.parse(inspect.getsource(pyjinhx._component))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "_component.py must not use relative imports"
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert name not in FORBIDDEN_IMPORTS, (
                f"_component.py must not import {name}"
            )
            assert not any(name.startswith(f"{f}.") for f in FORBIDDEN_IMPORTS), (
                f"_component.py must not import {name}"
            )


class OpenCard(_OpenComponent):
    name: str


class StrictCard(BaseComponent):
    name: str


def test_open_component_declared_fields_behave_like_base_component():
    card = OpenCard(name="hello")
    assert card.name == "hello"
    assert card.id
    assert card.model_extra == {}


def test_open_component_accepts_undeclared_kwarg_into_model_extra():
    card = OpenCard(name="hello", data_testid="card-1")  # pyright: ignore[reportCallIssue]
    assert card.model_extra == {"data_testid": "card-1"}
    assert card.model_dump()["data_testid"] == "card-1"


def test_base_component_still_rejects_undeclared_kwarg():
    with pytest.raises(ValidationError):
        StrictCard(name="hello", data_testid="card-1")  # pyright: ignore[reportCallIssue]


def test_open_subclass_is_not_strict_and_base_subclass_is():
    assert OpenCard.__pjx_descriptor__.strict is False
    assert StrictCard.__pjx_descriptor__.strict is True


def test_open_subclass_still_enforces_reserved_id_field():
    with pytest.raises(TypeError, match="redeclares the reserved id field"):

        class BadOpen(_OpenComponent):
            id: int = 0  # pyright: ignore[reportIncompatibleVariableOverride]
