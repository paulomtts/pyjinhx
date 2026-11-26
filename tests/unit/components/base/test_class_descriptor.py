"""Tests for resolving, attaching and rebuilding a component's ClassDescriptor."""

import sys
import types
from pathlib import Path
from typing import Annotated, ClassVar, Optional

import pytest
from pydantic import ConfigDict

import pyjinhx.components.base
from pyjinhx.components.base import (
    BaseComponent,
    Children,
    ClassDescriptor,
    PjxSlot,
    Slot,
    _defining_module_dir,
    _resolve_class_descriptor,
    _resolve_slot_fields,
    _resolve_strict,
    rebuild_class_descriptor,
)
from tests.unit.components.base._mro_module import _MRO_MODULE


class TestResolveClassDescriptor:
    """The seam every resolver lands behind: one call, one whole ClassDescriptor."""

    def test_returns_a_fully_constructed_descriptor(self):
        """`provenance` is empty here, and every path field is empty or
        unproven for the same reason: `Card` is a direct subclass whose sole
        template candidate is the last ancestor's — returned unprobed per
        ADR 0007 — and no `card.pjx`, `card.css` or `card.js` sits beside this
        test file. Nothing was proven to exist, so no ancestor is named."""

        class Card(BaseComponent):
            pass

        descriptor = _resolve_class_descriptor(Card)

        assert isinstance(descriptor, ClassDescriptor)
        assert descriptor.template_path == Path(__file__).parent / "card.pjx"
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


class TestResolveSlotFields:
    """#275: `slot_fields` is the set of declared fields that are slots — a
    type-level fact computed once at registration. Which single field receives
    a PascalCase tag's children (the precedence rules) is L1's job, not this
    one; per-field marker mechanics are covered in rendering/template_context/test_slot_type.py."""

    def test_no_fields_means_no_slots(self):
        class Card(BaseComponent):
            pass

        assert _resolve_slot_fields(Card) == frozenset()

    def test_single_slot_typed_field(self):
        class Panel(BaseComponent):
            body: Slot = ""

        assert _resolve_slot_fields(Panel) == frozenset({"body"})

    def test_children_alias_counts_as_a_slot(self):
        class Wrapper(BaseComponent):
            inner: Children = ""

        assert _resolve_slot_fields(Wrapper) == frozenset({"inner"})

    def test_multiple_slot_typed_fields(self):
        class Layout(BaseComponent):
            header: Slot = ""
            body: Children = ""
            footer: Slot = ""

        assert _resolve_slot_fields(Layout) == frozenset({"header", "body", "footer"})

    def test_designated_children_field_without_a_slot_type(self):
        """`_pjx_children_field` names a plain `str` field: it is a slot anyway.
        The `ClassVar[str]` annotation is mandatory — `BaseComponent` does not
        declare `_pjx_children_field`, so an unannotated assignment becomes a
        pydantic private attribute and the name comparison silently fails."""

        class Designated(BaseComponent):
            _pjx_children_field: ClassVar[str | None] = "kids"
            kids: str = ""

        assert _resolve_slot_fields(Designated) == frozenset({"kids"})

    def test_slot_typed_and_designated_field_union(self):
        class Both(BaseComponent):
            _pjx_children_field: ClassVar[str | None] = "kids"
            kids: str = ""
            body: Slot = ""

        assert _resolve_slot_fields(Both) == frozenset({"kids", "body"})

    def test_inherited_slot_field_is_included(self):
        class Base(BaseComponent):
            body: Slot = ""

        class Child(Base):
            title: str = ""

        assert _resolve_slot_fields(Child) == frozenset({"body"})

    def test_only_slot_names_not_every_field(self):
        """Guards against over-inclusion: `id` and the plain scalars must not
        leak into the set."""

        class Mixed(BaseComponent):
            label: str = ""
            count: int = 0
            body: Slot = ""

        assert _resolve_slot_fields(Mixed) == frozenset({"body"})
        assert "id" not in _resolve_slot_fields(Mixed)

    def test_extra_keys_are_never_walked(self):
        """ADR 0006: detection reads `model_fields` only. An open subclass that
        accepts undeclared kwargs still reports only its declared slot."""

        class Open(BaseComponent):
            model_config = {"extra": "allow"}  # noqa: RUF012 — pydantic's own ConfigDict pattern
            body: Slot = ""

        instance = Open(
            body="<b>hi</b>",
            surprise="<i>x</i>",  # pyright: ignore[reportCallIssue]
        )

        assert instance.model_extra == {"surprise": "<i>x</i>"}
        assert _resolve_slot_fields(Open) == frozenset({"body"})

    def test_descriptor_carries_the_resolved_set(self):
        """End-to-end through the registration seam, not just the helper."""

        class Panel(BaseComponent):
            body: Slot = ""
            title: str = ""

        assert _resolve_class_descriptor(Panel).slot_fields == frozenset({"body"})
        assert Panel.__pjx_descriptor__.slot_fields == frozenset({"body"})

    def test_bare_component_field_is_auto_detected(self):
        class Leaf(BaseComponent):
            pass

        class Card(BaseComponent):
            child: Leaf | None = None

        assert _resolve_slot_fields(Card) == frozenset({"child"})

    def test_optional_component_field_is_auto_detected(self):
        class Leaf(BaseComponent):
            pass

        class Card(BaseComponent):
            child: Optional[Leaf] = None  # noqa: UP045 — exercising Optional[], not just X | None

        assert _resolve_slot_fields(Card) == frozenset({"child"})

    def test_component_list_field_is_auto_detected(self):
        class Badge(BaseComponent):
            pass

        class Card(BaseComponent):
            badges: list[Badge] = []  # noqa: RUF012 — pydantic's own default-factory handling

        assert _resolve_slot_fields(Card) == frozenset({"badges"})

    def test_component_dict_field_is_auto_detected(self):
        class Badge(BaseComponent):
            pass

        class Card(BaseComponent):
            named: dict[str, Badge] = {}  # noqa: RUF012 — pydantic's own default-factory handling

        assert _resolve_slot_fields(Card) == frozenset({"named"})

    def test_plain_string_field_needs_an_explicit_marker(self):
        class Card(BaseComponent):
            caption: str = ""

        assert _resolve_slot_fields(Card) == frozenset()

    def test_mixed_union_field_is_not_auto_detected(self):
        class Leaf(BaseComponent):
            pass

        class Card(BaseComponent):
            either: str | Leaf = ""

        assert _resolve_slot_fields(Card) == frozenset()

    def test_explicit_marker_on_a_component_field_still_counts(self):
        class Leaf(BaseComponent):
            pass

        class Card(BaseComponent):
            child: Annotated[Leaf | None, PjxSlot()] = None

        assert _resolve_slot_fields(Card) == frozenset({"child"})

    def test_auto_detected_and_explicit_fields_are_unioned(self):
        class Leaf(BaseComponent):
            pass

        class Card(BaseComponent):
            child: Leaf | None = None  # auto-detected
            html: Slot = ""  # explicit string slot
            caption: str = ""  # neither

        assert _resolve_slot_fields(Card) == frozenset({"child", "html"})

    def test_plain_string_children_field_is_unaffected(self):
        class Card(BaseComponent):
            _pjx_children_field: ClassVar[str | None] = "kids"
            kids: str = ""

        assert _resolve_slot_fields(Card) == frozenset({"kids"})

    def test_only_declared_fields_are_considered(self):
        class Leaf(BaseComponent):
            pass

        class Card(BaseComponent):
            model_config = ConfigDict(extra="allow")
            child: Leaf | None = None

        assert _resolve_slot_fields(Card) <= frozenset(Card.model_fields)


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
        """A class with no module on disk has no directory to probe from: this
        fails loudly here rather than inventing a path. The template and asset
        candidate builders both route through this guard rather than
        inventing a path of their own."""
        module = types.ModuleType("pyjinhx_test_fileless_module")
        sys.modules["pyjinhx_test_fileless_module"] = module
        try:

            class Card(BaseComponent):
                pass

            Card.__module__ = "pyjinhx_test_fileless_module"
            with pytest.raises(NotImplementedError, match="no file on disk"):
                _defining_module_dir(Card)
        finally:
            del sys.modules["pyjinhx_test_fileless_module"]


class TestDescriptorAttachedAtClassDefinition:
    def test_a_subclass_gets_a_class_descriptor(self):
        class Card(BaseComponent):
            pass

        assert isinstance(Card.__pjx_descriptor__, ClassDescriptor)

    def test_base_component_itself_has_no_descriptor(self):
        """Pydantic does not fire __pydantic_init_subclass__ for the class that
        defines it. Relied on, not special-cased."""
        assert "__pjx_descriptor__" not in vars(BaseComponent)

    def test_the_seam_is_called_exactly_once_per_class_definition(self, monkeypatch):
        calls: list[type] = []
        real = pyjinhx.components.base._resolve_class_descriptor

        def counting(cls):
            calls.append(cls)
            return real(cls)

        monkeypatch.setattr(
            pyjinhx.components.base, "_resolve_class_descriptor", counting
        )

        class Card(BaseComponent):
            pass

        Card()
        Card()

        assert calls == [Card]

    def test_the_descriptor_is_the_same_object_across_instantiations(self):
        class Card(BaseComponent):
            pass

        first, second = Card(), Card()

        assert first.__pjx_descriptor__ is second.__pjx_descriptor__
        assert first.__pjx_descriptor__ is Card.__pjx_descriptor__

    def test_sibling_subclasses_get_distinct_descriptors(self):
        class Card(BaseComponent):
            pass

        class Banner(BaseComponent):
            pass

        assert Card.__pjx_descriptor__ is not Banner.__pjx_descriptor__
        assert (
            Card.__pjx_descriptor__.template_path
            != Banner.__pjx_descriptor__.template_path
        )

    def test_a_subclass_of_a_subclass_gets_its_own_descriptor(self):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        assert FancyCard.__pjx_descriptor__ is not Card.__pjx_descriptor__
        assert "__pjx_descriptor__" in vars(FancyCard)

    def test_the_descriptor_is_not_a_model_field(self):
        class Card(BaseComponent):
            pass

        assert "__pjx_descriptor__" not in Card.model_fields

    def test_registration_goes_through_the_rebuild_entry_point(self, monkeypatch):
        """One assignment site for `__pjx_descriptor__`: registration and
        dev-reload cannot drift apart because they are the same call."""
        seen: list[type] = []
        real = pyjinhx.components.base.rebuild_class_descriptor

        def spying(cls):
            seen.append(cls)
            real(cls)

        monkeypatch.setattr(pyjinhx.components.base, "rebuild_class_descriptor", spying)

        class Card(BaseComponent):
            pass

        assert seen == [Card]
        assert isinstance(Card.__pjx_descriptor__, ClassDescriptor)


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
            pyjinhx.components.base,
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
        real = pyjinhx.components.base._resolve_class_descriptor

        def spying(cls):
            seen.append(frozenset(cls.model_fields))
            return real(cls)

        monkeypatch.setattr(
            pyjinhx.components.base, "_resolve_class_descriptor", spying
        )

        class Card(BaseComponent):
            title: str = ""

        assert seen == [frozenset({"id", "title"})]


class TestSeamFailurePropagates:
    def test_a_raising_seam_aborts_the_class_statement(self, monkeypatch):
        def boom(cls):
            raise NotImplementedError("resolver not implemented yet")

        monkeypatch.setattr(pyjinhx.components.base, "_resolve_class_descriptor", boom)

        with pytest.raises(NotImplementedError, match="resolver not implemented yet"):

            class Card(BaseComponent):
                pass

    def test_a_class_defined_in_a_fileless_module_fails_at_definition_time(self):
        module = types.ModuleType("pyjinhx_test_fileless_defining_module")
        module.BaseComponent = BaseComponent  # pyright: ignore[reportAttributeAccessIssue]
        sys.modules["pyjinhx_test_fileless_defining_module"] = module
        try:
            with pytest.raises(NotImplementedError, match="no file on disk"):
                exec(  # noqa: S102 — only way to define a class in a fileless module
                    "class Card(BaseComponent):\n    pass\n",
                    module.__dict__,
                )
        finally:
            del sys.modules["pyjinhx_test_fileless_defining_module"]


class TestDevReloadReassignmentSmokeTest:
    def test_the_attribute_can_be_replaced_wholesale(self):
        """#278's dev-reload rebuild replaces the whole descriptor object. The
        ClassDescriptor is frozen; the class attribute pointing at it is not, so
        this needs no unlock beyond a plain attribute set."""

        class Card(BaseComponent):
            pass

        original = Card.__pjx_descriptor__
        replacement = ClassDescriptor(
            template_path=Path("rebuilt/card.pjx"),
            slot_fields=frozenset({"body"}),
            children_field=None,
            css_paths=(Path("rebuilt/card.css"),),
            js_paths=(),
            strict=True,
            provenance={"template": Card},
        )

        Card.__pjx_descriptor__ = replacement

        assert Card.__pjx_descriptor__ is replacement
        assert Card.__pjx_descriptor__ is not original


class TestRebuildClassDescriptor:
    """The single post-registration recomputation point (invariant 5). It swaps
    a whole new descriptor in; it watches nothing and triggers nothing itself."""

    def test_an_unchanged_class_rebuilds_to_an_equal_descriptor(self):
        class Card(BaseComponent):
            pass

        original = Card.__pjx_descriptor__

        rebuild_class_descriptor(Card)

        assert Card.__pjx_descriptor__ == original

    def test_the_rebuilt_descriptor_is_a_new_object(self):
        """Frozen dataclass: the only way to rebuild is build-then-swap, so an
        equal descriptor must still be a different object."""

        class Card(BaseComponent):
            pass

        original = Card.__pjx_descriptor__

        rebuild_class_descriptor(Card)

        assert Card.__pjx_descriptor__ is not original

    def test_the_previous_descriptor_is_left_untouched(self):
        class Card(BaseComponent):
            pass

        original = Card.__pjx_descriptor__
        snapshot = (
            original.template_path,
            original.slot_fields,
            original.css_paths,
            original.js_paths,
            original.strict,
            dict(original.provenance),
        )

        rebuild_class_descriptor(Card)

        assert (
            original.template_path,
            original.slot_fields,
            original.css_paths,
            original.js_paths,
            original.strict,
            dict(original.provenance),
        ) == snapshot

    def test_rebuilding_twice_does_not_drift(self):
        class Card(BaseComponent):
            pass

        original = Card.__pjx_descriptor__

        rebuild_class_descriptor(Card)
        first = Card.__pjx_descriptor__
        rebuild_class_descriptor(Card)
        second = Card.__pjx_descriptor__

        assert first == original
        assert second == original
        assert second is not first

    def test_it_returns_none(self):
        class Card(BaseComponent):
            pass

        assert rebuild_class_descriptor(Card) is None

    def test_a_template_that_appeared_on_disk_is_picked_up(self, mro_dir):
        """Same resolver, fresh inputs: with no file present the walk falls back
        to the last ancestor's unprobed candidate; once `fancy_card.pjx` exists
        the nearest ancestor wins and is named in provenance."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        rebuild_class_descriptor(FancyCard)
        before = FancyCard.__pjx_descriptor__

        (mro_dir / "fancy_card.pjx").write_text("<div></div>", encoding="utf-8")
        rebuild_class_descriptor(FancyCard)
        after = FancyCard.__pjx_descriptor__

        assert before.template_path == mro_dir / "card.pjx"
        assert before.provenance == {}
        assert after.template_path == mro_dir / "fancy_card.pjx"
        assert after.provenance == {"template": FancyCard}
        assert after != before

    def test_an_asset_that_appeared_on_disk_is_picked_up(self, mro_dir):
        class Card(BaseComponent):
            pass

        Card.__module__ = _MRO_MODULE

        rebuild_class_descriptor(Card)
        assert Card.__pjx_descriptor__.css_paths == ()

        (mro_dir / "card.css").write_text("a{}", encoding="utf-8")
        rebuild_class_descriptor(Card)

        assert Card.__pjx_descriptor__.css_paths == (mro_dir / "card.css",)
        assert Card.__pjx_descriptor__.provenance["css"] is Card

    def test_it_delegates_to_the_shared_resolver(self, monkeypatch):
        """No parallel resolution logic: whatever `_resolve_class_descriptor`
        returns is exactly what lands on the class."""

        class Card(BaseComponent):
            pass

        sentinel = ClassDescriptor(
            template_path=Path("sentinel/card.pjx"),
            slot_fields=frozenset(),
            children_field=None,
            css_paths=(),
            js_paths=(),
            strict=True,
            provenance={},
        )
        monkeypatch.setattr(
            pyjinhx.components.base, "_resolve_class_descriptor", lambda cls: sentinel
        )

        rebuild_class_descriptor(Card)

        assert Card.__pjx_descriptor__ is sentinel
