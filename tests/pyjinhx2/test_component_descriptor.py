import sys
import types
from pathlib import Path

import pytest

import pyjinhx2.component
from pyjinhx2.component import (
    BaseComponent,
    _defining_module_dir,
    _pascal_to_snake,
    _resolve_class_descriptor,
    _resolve_strict,
)
from pyjinhx2.descriptor import ClassDescriptor


class TestResolveClassDescriptor:
    """The seam #272-#276 land behind: one call, one whole ClassDescriptor."""

    def test_returns_a_fully_constructed_descriptor(self):
        class Card(BaseComponent):
            pass

        descriptor = _resolve_class_descriptor(Card)

        assert isinstance(descriptor, ClassDescriptor)
        assert descriptor.template_path == Path(__file__).parent / "Card.pjx"
        assert descriptor.slot_fields == frozenset()
        assert descriptor.css_paths == ()
        assert descriptor.js_paths == ()
        assert descriptor.strict is True
        assert descriptor.provenance == {}

    def test_each_call_builds_a_new_object(self):
        """The seam itself is pure and uncached; the caching is the hook's job
        (one call per class definition), which Task 2 covers."""

        class Card(BaseComponent):
            pass

        assert _resolve_class_descriptor(Card) is not _resolve_class_descriptor(Card)


class TestResolveStrict:
    """strict is real data today, not a stub: it reads the ADR 0006 mode off
    the class's own pydantic config, so L1's open subclass flips it for free."""

    def test_true_for_the_closed_core(self):
        class Card(BaseComponent):
            pass

        assert _resolve_strict(Card) is True

    def test_false_when_a_subclass_reopens_extras(self):
        class Open(BaseComponent):
            model_config = {"extra": "allow"}  # noqa: RUF012 — pydantic's own ConfigDict pattern

        assert _resolve_strict(Open) is False


class TestDefiningModuleDir:
    def test_returns_the_directory_of_the_defining_module(self):
        class Card(BaseComponent):
            pass

        assert _defining_module_dir(Card) == Path(__file__).parent

    def test_raises_not_implemented_when_the_module_has_no_file(self):
        """A class with no module on disk has no directory to probe from. #271
        fails loudly here rather than inventing a path; #272/#276 inherit the
        guard when they replace the stubs."""
        module = types.ModuleType("pyjinhx2_test_fileless_module")
        sys.modules["pyjinhx2_test_fileless_module"] = module
        try:

            class Card(BaseComponent):
                pass

            Card.__module__ = "pyjinhx2_test_fileless_module"
            with pytest.raises(NotImplementedError, match="no file on disk"):
                _defining_module_dir(Card)
        finally:
            del sys.modules["pyjinhx2_test_fileless_module"]


class TestDescriptorAttachedAtClassDefinition:
    def test_a_subclass_gets_a_class_descriptor(self):
        class Card(BaseComponent):
            pass

        assert isinstance(Card._pjx_descriptor, ClassDescriptor)

    def test_base_component_itself_has_no_descriptor(self):
        """Pydantic does not fire __pydantic_init_subclass__ for the class that
        defines it. Relied on, not special-cased."""
        assert "_pjx_descriptor" not in vars(BaseComponent)

    def test_the_seam_is_called_exactly_once_per_class_definition(self, monkeypatch):
        calls: list[type] = []
        real = pyjinhx2.component._resolve_class_descriptor

        def counting(cls):
            calls.append(cls)
            return real(cls)

        monkeypatch.setattr(pyjinhx2.component, "_resolve_class_descriptor", counting)

        class Card(BaseComponent):
            pass

        Card()
        Card()

        assert calls == [Card]

    def test_the_descriptor_is_the_same_object_across_instantiations(self):
        class Card(BaseComponent):
            pass

        first, second = Card(), Card()

        assert first._pjx_descriptor is second._pjx_descriptor
        assert first._pjx_descriptor is Card._pjx_descriptor

    def test_sibling_subclasses_get_distinct_descriptors(self):
        class Card(BaseComponent):
            pass

        class Banner(BaseComponent):
            pass

        assert Card._pjx_descriptor is not Banner._pjx_descriptor
        assert (
            Card._pjx_descriptor.template_path != Banner._pjx_descriptor.template_path
        )

    def test_a_subclass_of_a_subclass_gets_its_own_descriptor(self):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        assert FancyCard._pjx_descriptor is not Card._pjx_descriptor
        assert "_pjx_descriptor" in vars(FancyCard)

    def test_the_descriptor_is_not_a_model_field(self):
        class Card(BaseComponent):
            pass

        assert "_pjx_descriptor" not in Card.model_fields


class TestHookOrdering:
    def test_reserved_auto_id_field_still_raises(self):
        with pytest.raises(TypeError, match="auto_id must remain a ClassVar"):

            class Bad(BaseComponent):
                auto_id: bool = True  # pyright: ignore[reportIncompatibleVariableOverride]

    def test_redeclaring_id_with_a_non_str_type_still_raises(self):
        with pytest.raises(TypeError, match="redeclares the reserved id field"):

            class Bad(BaseComponent):
                id: int = 0  # pyright: ignore[reportIncompatibleVariableOverride]

    def test_the_seam_does_not_run_when_reserved_name_validation_fails(
        self, monkeypatch
    ):
        """The attach step comes after the reserved-name checks, so a rejected
        class never reaches the resolver."""
        calls: list[type] = []
        monkeypatch.setattr(
            pyjinhx2.component,
            "_resolve_class_descriptor",
            lambda cls: calls.append(cls),
        )

        with pytest.raises(TypeError):

            class Bad(BaseComponent):
                auto_id: bool = True  # pyright: ignore[reportIncompatibleVariableOverride]

        assert calls == []

    def test_the_seam_runs_after_super_has_built_model_fields(self, monkeypatch):
        """super().__pydantic_init_subclass__(**kwargs) is still called first:
        by the time the seam sees the class, pydantic has finished building it."""
        seen: list[frozenset[str]] = []
        real = pyjinhx2.component._resolve_class_descriptor

        def spying(cls):
            seen.append(frozenset(cls.model_fields))
            return real(cls)

        monkeypatch.setattr(pyjinhx2.component, "_resolve_class_descriptor", spying)

        class Card(BaseComponent):
            title: str = ""

        assert seen == [frozenset({"id", "title"})]


class TestSeamFailurePropagates:
    def test_a_raising_seam_aborts_the_class_statement(self, monkeypatch):
        def boom(cls):
            raise NotImplementedError("resolver not implemented yet")

        monkeypatch.setattr(pyjinhx2.component, "_resolve_class_descriptor", boom)

        with pytest.raises(NotImplementedError, match="resolver not implemented yet"):

            class Card(BaseComponent):
                pass

    def test_a_class_defined_in_a_fileless_module_fails_at_definition_time(self):
        module = types.ModuleType("pyjinhx2_test_fileless_defining_module")
        module.BaseComponent = BaseComponent  # pyright: ignore[reportAttributeAccessIssue]
        sys.modules["pyjinhx2_test_fileless_defining_module"] = module
        try:
            with pytest.raises(NotImplementedError, match="no file on disk"):
                exec(  # noqa: S102 — only way to define a class in a fileless module
                    "class Card(BaseComponent):\n    pass\n",
                    module.__dict__,
                )
        finally:
            del sys.modules["pyjinhx2_test_fileless_defining_module"]


class TestDevReloadReassignmentSmokeTest:
    def test_the_attribute_can_be_replaced_wholesale(self):
        """#278's dev-reload rebuild replaces the whole descriptor object. The
        ClassDescriptor is frozen; the class attribute pointing at it is not, so
        this needs no unlock beyond a plain attribute set."""

        class Card(BaseComponent):
            pass

        original = Card._pjx_descriptor
        replacement = ClassDescriptor(
            template_path=Path("rebuilt/card.pjx"),
            slot_fields=frozenset({"body"}),
            css_paths=(Path("rebuilt/card.css"),),
            js_paths=(),
            strict=True,
            provenance={"template": Card},
        )

        Card._pjx_descriptor = replacement

        assert Card._pjx_descriptor is replacement
        assert Card._pjx_descriptor is not original


class TestPascalToSnake:
    """The ADR 0007 filename convention: acronym-aware PascalCase -> snake_case,
    matching v0.x's pyjinhx/utils.py:pascal_case_to_snake_case exactly, but
    reimplemented locally because pyjinhx2 must not import the legacy package."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Card", "card"),
            ("ScrollSentinel", "scroll_sentinel"),
            ("PJXButton", "pjx_button"),
            ("HTMLParser", "html_parser"),
            ("PJX", "pjx"),
            ("TabPanelPJX", "tab_panel_pjx"),
            ("Grid2Col", "grid2_col"),
            ("A", "a"),
            ("already_snake", "already_snake"),
        ],
    )
    def test_converts_pascal_case_to_snake_case(self, name, expected):
        assert _pascal_to_snake(name) == expected
