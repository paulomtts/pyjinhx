import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

import pytest

import pyjinhx2.component
from pyjinhx2.component import (
    BaseComponent,
    Children,
    Slot,
    TemplateNotFoundError,
    _asset_candidate,
    _defining_module_dir,
    _pascal_to_snake,
    _resolution_ancestors,
    _resolve_asset_paths,
    _resolve_class_descriptor,
    _resolve_provenance,
    _resolve_slot_fields,
    _resolve_strict,
    _resolve_template_path,
    _template_candidate,
    _walk_template,
    rebuild_class_descriptor,
)
from pyjinhx2.descriptor import ClassDescriptor


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
    one; per-field marker mechanics are covered in test_slot_type_v2.py."""

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
            _pjx_children_field: ClassVar[str] = "kids"
            kids: str = ""

        assert _resolve_slot_fields(Designated) == frozenset({"kids"})

    def test_slot_typed_and_designated_field_union(self):
        class Both(BaseComponent):
            _pjx_children_field: ClassVar[str] = "kids"
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
        assert Panel._pjx_descriptor.slot_fields == frozenset({"body"})


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

    def test_registration_goes_through_the_rebuild_entry_point(self, monkeypatch):
        """One assignment site for `_pjx_descriptor`: registration and
        dev-reload cannot drift apart because they are the same call."""
        seen: list[type] = []
        real = pyjinhx2.component.rebuild_class_descriptor

        def spying(cls):
            seen.append(cls)
            real(cls)

        monkeypatch.setattr(pyjinhx2.component, "rebuild_class_descriptor", spying)

        class Card(BaseComponent):
            pass

        assert seen == [Card]
        assert isinstance(Card._pjx_descriptor, ClassDescriptor)


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


class TestRebuildClassDescriptor:
    """The single post-registration recomputation point (invariant 5). It swaps
    a whole new descriptor in; it watches nothing and triggers nothing itself."""

    def test_an_unchanged_class_rebuilds_to_an_equal_descriptor(self):
        class Card(BaseComponent):
            pass

        original = Card._pjx_descriptor

        rebuild_class_descriptor(Card)

        assert Card._pjx_descriptor == original

    def test_the_rebuilt_descriptor_is_a_new_object(self):
        """Frozen dataclass: the only way to rebuild is build-then-swap, so an
        equal descriptor must still be a different object."""

        class Card(BaseComponent):
            pass

        original = Card._pjx_descriptor

        rebuild_class_descriptor(Card)

        assert Card._pjx_descriptor is not original

    def test_the_previous_descriptor_is_left_untouched(self):
        class Card(BaseComponent):
            pass

        original = Card._pjx_descriptor
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

        original = Card._pjx_descriptor

        rebuild_class_descriptor(Card)
        first = Card._pjx_descriptor
        rebuild_class_descriptor(Card)
        second = Card._pjx_descriptor

        assert first == original
        assert second == original
        assert second is not first

    def test_it_returns_none(self):
        class Card(BaseComponent):
            pass

        assert rebuild_class_descriptor(Card) is None

    def test_a_template_that_appeared_on_disk_is_picked_up(self, mro_dir):
        """Same resolver, fresh inputs: with no ancestor file present the walk
        falls back to the root ancestor's candidate; once `fancy_card.pjx`
        exists the nearest ancestor wins and is named in provenance. `Card`
        gets its own template up front — a component must have one to
        register at all — so the only thing that changes across the two
        rebuilds is whether `FancyCard`'s own candidate exists."""
        (mro_dir / "card.pjx").write_text("<div></div>", encoding="utf-8")

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        rebuild_class_descriptor(FancyCard)
        before = FancyCard._pjx_descriptor

        (mro_dir / "fancy_card.pjx").write_text("<div></div>", encoding="utf-8")
        rebuild_class_descriptor(FancyCard)
        after = FancyCard._pjx_descriptor

        assert before.template_path == mro_dir / "card.pjx"
        assert before.provenance == {}
        assert after.template_path == mro_dir / "fancy_card.pjx"
        assert after.provenance == {"template": FancyCard}
        assert after != before

    def test_an_asset_that_appeared_on_disk_is_picked_up(self, mro_dir):
        """`Card` gets its own template up front so it can register at all;
        the CSS candidate is unrelated to that guard and stays optional."""
        (mro_dir / "card.pjx").write_text("<div></div>", encoding="utf-8")

        class Card(BaseComponent):
            pass

        Card.__module__ = _MRO_MODULE

        rebuild_class_descriptor(Card)
        assert Card._pjx_descriptor.css_paths == ()

        (mro_dir / "card.css").write_text("a{}", encoding="utf-8")
        rebuild_class_descriptor(Card)

        assert Card._pjx_descriptor.css_paths == (mro_dir / "card.css",)
        assert Card._pjx_descriptor.provenance["css"] is Card

    def test_it_delegates_to_the_shared_resolver(self, monkeypatch):
        """No parallel resolution logic: whatever `_resolve_class_descriptor`
        returns is exactly what lands on the class."""

        class Card(BaseComponent):
            pass

        sentinel = ClassDescriptor(
            template_path=Path("sentinel/card.pjx"),
            slot_fields=frozenset(),
            css_paths=(),
            js_paths=(),
            strict=True,
            provenance={},
        )
        monkeypatch.setattr(
            pyjinhx2.component, "_resolve_class_descriptor", lambda cls: sentinel
        )

        rebuild_class_descriptor(Card)

        assert Card._pjx_descriptor is sentinel


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


class TestAssetCandidate:
    """ADR 0007's one convention, asset half: snake_case class name plus the
    kind's extension, beside the defining module. No kebab-case fallback."""

    def test_it_uses_the_snake_case_class_name_and_the_kind_extension(self, mro_dir):
        """`FancyCard` needs its own template to register at all; the asset
        candidate path arithmetic under test here is independent of that."""
        (mro_dir / "fancy_card.pjx").write_text("<div></div>", encoding="utf-8")

        class FancyCard(BaseComponent):
            __module__ = _MRO_MODULE

        assert _asset_candidate(FancyCard, "css") == mro_dir / "fancy_card.css"
        assert _asset_candidate(FancyCard, "js") == mro_dir / "fancy_card.js"

    def test_it_sits_beside_the_template_candidate(self):
        class Card(BaseComponent):
            pass

        assert _asset_candidate(Card, "css").parent == _template_candidate(Card).parent


class TestResolveTemplatePath:
    """ADR 0007: one candidate — snake_case(class name) + `.pjx`, in the
    defining module's own directory. No MRO walk (#273), no existence check
    (#277 owns the missing-template error)."""

    def test_returns_snake_case_pjx_beside_the_defining_module(self):
        class Card(BaseComponent):
            pass

        assert _resolve_template_path(Card) == Path(__file__).parent / "card.pjx"

    def test_multi_word_class_names_are_snake_cased(self):
        class ScrollSentinel(BaseComponent):
            pass

        assert (
            _resolve_template_path(ScrollSentinel)
            == Path(__file__).parent / "scroll_sentinel.pjx"
        )

    def test_acronym_leading_class_names_are_snake_cased(self):
        class PJXButton(BaseComponent):
            pass

        assert (
            _resolve_template_path(PJXButton)
            == Path(__file__).parent / "pjx_button.pjx"
        )

    def test_the_directory_is_exactly_the_defining_module_dir(self):
        class Card(BaseComponent):
            pass

        assert _resolve_template_path(Card).parent == _defining_module_dir(Card)

    def test_the_only_extension_attempted_is_pjx(self):
        class Card(BaseComponent):
            pass

        path = _resolve_template_path(Card)

        assert path.suffix == ".pjx"
        assert path.name == "card.pjx"

    def test_the_path_is_returned_even_when_no_file_exists(self):
        """This subtask computes the path; it does not validate existence.
        Turning 'file absent' into an error is #277's job."""

        class NoSuchTemplateAnywhere(BaseComponent):
            pass

        path = _resolve_template_path(NoSuchTemplateAnywhere)

        assert not path.exists()
        assert path == Path(__file__).parent / "no_such_template_anywhere.pjx"

    def test_a_fileless_module_still_raises_not_implemented(self):
        """Regression guard: #272 must not catch or reword #271's guard."""
        module = types.ModuleType("pyjinhx2_test_fileless_template_module")
        sys.modules["pyjinhx2_test_fileless_template_module"] = module
        try:

            class Card(BaseComponent):
                pass

            Card.__module__ = "pyjinhx2_test_fileless_template_module"
            with pytest.raises(NotImplementedError, match="no file on disk"):
                _resolve_template_path(Card)
        finally:
            del sys.modules["pyjinhx2_test_fileless_template_module"]

    def test_it_never_touches_the_filesystem(self, monkeypatch):
        """ADR 0007 allows at most one probe; #272 needs zero, because it does
        not validate existence. Counting Path.exists calls pins that down so a
        later 'helpful' existence check has to be a deliberate change."""
        calls: list[Path] = []
        real_exists = Path.exists

        def counting(self, *args, **kwargs):
            calls.append(self)
            return real_exists(self, *args, **kwargs)

        monkeypatch.setattr(Path, "exists", counting)

        class Card(BaseComponent):
            pass

        _resolve_template_path(Card)

        assert calls == []


class TestResolutionAncestors:
    """ADR 0010's walk order: nearest first, stopping before BaseComponent —
    BaseComponent has no descriptor and is never probed for a template."""

    def test_a_direct_subclass_is_its_own_only_ancestor(self):
        class Card(BaseComponent):
            pass

        assert _resolution_ancestors(Card) == [Card]

    def test_a_chain_is_listed_nearest_first(self):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        assert _resolution_ancestors(VeryFancyCard) == [VeryFancyCard, FancyCard, Card]

    def test_base_component_is_excluded(self):
        class Card(BaseComponent):
            pass

        assert BaseComponent not in _resolution_ancestors(Card)

    def test_nothing_below_base_component_is_included(self):
        """object and BaseModel sit after BaseComponent in the MRO, so the
        truncation drops them too."""

        class Card(BaseComponent):
            pass

        assert all(issubclass(a, BaseComponent) for a in _resolution_ancestors(Card))


_MRO_MODULE = "pyjinhx2_test_mro_module"


@pytest.fixture
def mro_dir(tmp_path: Path) -> Iterator[Path]:
    """A real, file-backed module registered in sys.modules, plus its directory.

    Classes re-pointed at it with ``Cls.__module__ = _MRO_MODULE`` resolve their
    template candidates inside ``tmp_path``, so a test controls exactly which
    ancestors have a file on disk.
    """
    module = types.ModuleType(_MRO_MODULE)
    module.__file__ = str(tmp_path / f"{_MRO_MODULE}.py")
    sys.modules[_MRO_MODULE] = module
    try:
        yield tmp_path
    finally:
        del sys.modules[_MRO_MODULE]


class TestTemplateMroWalk:
    """ADR 0010: the nearest ancestor that actually has a `.pjx` on disk wins.
    One candidate per ancestor (ADR 0007), template kind only."""

    def test_an_own_file_wins_over_an_ancestors(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")

        assert _resolve_template_path(FancyCard) == mro_dir / "fancy_card.pjx"

    def test_a_parents_file_is_used_when_the_child_has_none(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")

        assert _resolve_template_path(FancyCard) == mro_dir / "card.pjx"

    def test_the_walk_hops_over_an_ancestor_with_no_file(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")

        assert _resolve_template_path(VeryFancyCard) == mro_dir / "card.pjx"

    def test_it_falls_back_to_the_root_ancestors_candidate(self, mro_dir):
        """No ancestor has a file: the root concrete ancestor's path is returned
        anyway. Whether that is an error is #277's call, not this walk's."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        path = _resolve_template_path(FancyCard)

        assert path == mro_dir / "card.pjx"
        assert not path.exists()

    def test_siblings_resolve_independently_to_the_same_parent(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class PlainCard(Card):
            pass

        for klass in (Card, FancyCard, PlainCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")

        assert _resolve_template_path(FancyCard) == mro_dir / "card.pjx"
        assert _resolve_template_path(PlainCard) == mro_dir / "card.pjx"


class TestWalkTemplate:
    """The single shared MRO walk both `_resolve_template_path` and
    `_resolve_provenance` consume: it returns the resolved path *and* the
    ancestor a probe proved owns it. The final fallback candidate is never
    probed (ADR 0007), so it can never be named as a winner."""

    def test_reports_the_owning_ancestor_when_a_probe_finds_a_file(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")

        assert _walk_template(FancyCard) == (mro_dir / "fancy_card.pjx", FancyCard)

    def test_reports_the_nearest_ancestor_with_a_file(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")

        assert _walk_template(VeryFancyCard) == (mro_dir / "fancy_card.pjx", FancyCard)

    def test_reports_no_winner_for_the_unprobed_fallback(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        assert _walk_template(FancyCard) == (mro_dir / "card.pjx", None)

    def test_a_direct_subclass_has_no_winner_because_nothing_is_probed(self):
        """`[cls]`'s only ancestor is also the last one, so it is returned
        unprobed — the walk never learns whether the file is there and so
        cannot name a winner."""

        class Card(BaseComponent):
            pass

        assert _walk_template(Card) == (Path(__file__).parent / "card.pjx", None)


class TestTemplateWalkProbeBudget:
    """ADR 0007's probe budget survives the walk: at most one `is_file` per
    ancestor, and none at all for the final fallback."""

    @staticmethod
    def _count_is_file(monkeypatch) -> list[Path]:
        probed: list[Path] = []
        real_is_file = Path.is_file

        def counting(self, *args, **kwargs):
            probed.append(self)
            return real_is_file(self, *args, **kwargs)

        monkeypatch.setattr(Path, "is_file", counting)
        return probed

    def test_a_direct_subclass_is_never_probed(self, monkeypatch):
        """The pinned zero-probe property, restated for `is_file`: for `[cls]`
        the only ancestor is also the last one.

        `Card` is defined before the spy is installed: registration's own
        `_resolve_class_descriptor` call now also walks css/js for `Card`
        (the asset walk probes every ancestor, unlike the template walk), and
        this test only wants to pin the *template* walk's zero-probe count."""

        class Card(BaseComponent):
            pass

        probed = self._count_is_file(monkeypatch)

        _resolve_template_path(Card)

        assert probed == []

    def test_the_last_ancestors_candidate_is_never_probed(self, mro_dir, monkeypatch):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        probed = self._count_is_file(monkeypatch)

        path = _resolve_template_path(FancyCard)

        assert path == mro_dir / "card.pjx"
        assert probed == [mro_dir / "fancy_card.pjx"]

    def test_the_walk_stops_at_the_first_hit(self, mro_dir, monkeypatch):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")
        probed = self._count_is_file(monkeypatch)

        path = _resolve_template_path(VeryFancyCard)

        assert path == mro_dir / "fancy_card.pjx"
        assert probed == [mro_dir / "very_fancy_card.pjx", mro_dir / "fancy_card.pjx"]


class TestTemplateWalkStopsAtBaseComponent:
    def test_base_component_is_never_considered(self, monkeypatch):
        """BaseComponent has no descriptor and no template; the walk must never
        ask for its directory, let alone probe `base_component.pjx`.

        The spy is installed *after* both classes are defined, not before:
        `__pydantic_init_subclass__` calls `_resolve_class_descriptor` (and so
        `_resolve_template_path`) for every class at its own definition, so a
        spy installed earlier also captures Card's and FancyCard's own
        registration-time walks and the assertion below would see several more
        entries than the one explicit call this test means to observe.
        """

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        considered: list[type] = []
        real = pyjinhx2.component._defining_module_dir

        def spying(cls):
            considered.append(cls)
            return real(cls)

        monkeypatch.setattr(pyjinhx2.component, "_defining_module_dir", spying)

        _resolve_template_path(FancyCard)

        assert BaseComponent not in considered
        assert considered == [FancyCard, Card]


class TestResolveProvenance:
    """ADR 0010: the descriptor records *which ancestor* supplied each kind —
    free provenance for error messages and the dependency graph. One entry per
    kind that actually resolved to a proven file; kinds that resolved to
    nothing name nobody."""

    def test_an_own_file_names_the_class_itself(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")

        assert _resolve_provenance(FancyCard) == {"template": FancyCard}

    def test_an_inherited_file_names_the_parent(self, mro_dir):
        """The found ancestor (`Card`) must not be the walk's own terminal
        candidate, or it would never get probed (see "Key design consequence"
        above). `Base` supplies the never-probed terminal slot instead."""

        class Base(BaseComponent):
            pass

        class Card(Base):
            pass

        class FancyCard(Card):
            pass

        Base.__module__ = _MRO_MODULE
        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")

        assert _resolve_provenance(FancyCard) == {"template": Card}

    def test_it_names_the_grandparent_over_a_fileless_parent(self, mro_dir):
        """Same terminal-slot caveat as above, one generation deeper: `Base`
        is the unprobed terminal, `Card` is the grandparent whose file a
        probe actually proves, `FancyCard` is the fileless middle ancestor
        that gets skipped."""

        class Base(BaseComponent):
            pass

        class Card(Base):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Base, Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")

        assert _resolve_provenance(VeryFancyCard) == {"template": Card}

    def test_no_template_key_when_no_ancestor_has_a_file(self, mro_dir):
        """`_resolve_template_path` still answers with the root ancestor's
        candidate (whether that is an error is #277's call), but that candidate
        is never probed — there is no ancestor proven to own a file, so naming
        one would be provenance for a file that does not exist."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        provenance = _resolve_provenance(FancyCard)

        assert provenance == {}
        assert "template" not in provenance

    def test_a_direct_subclass_gets_no_template_key(self):
        """Consequence of the ADR 0007 budget, stated outright: for `[cls]` the
        sole candidate is the unprobed fallback, so provenance is empty even
        when the file happens to exist."""

        class Card(BaseComponent):
            pass

        assert _resolve_provenance(Card) == {}

    def test_siblings_resolve_independently_to_the_same_parent(self, mro_dir):
        """Same terminal-slot caveat: `Base` is the unprobed terminal so that
        `Card`'s file is actually probed and can be named for both siblings."""

        class Base(BaseComponent):
            pass

        class Card(Base):
            pass

        class FancyCard(Card):
            pass

        class PlainCard(Card):
            pass

        for klass in (Base, Card, FancyCard, PlainCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")

        assert _resolve_provenance(FancyCard) == {"template": Card}
        assert _resolve_provenance(PlainCard) == {"template": Card}

    def test_base_component_is_never_named(self, mro_dir):
        """`_resolution_ancestors` truncates before BaseComponent, so it is out
        of the list before the walk starts — it can never be a provenance value
        even when nothing else on the chain has a file.

        Uses a real winning ancestor (`Card`, via the `Base` terminal-slot
        pattern above) rather than checking against an always-empty mapping:
        `BaseComponent not in {}` would hold trivially and prove nothing."""

        class Base(BaseComponent):
            pass

        class Card(Base):
            pass

        class FancyCard(Card):
            pass

        Base.__module__ = _MRO_MODULE
        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")

        assert _resolve_provenance(FancyCard) == {"template": Card}
        assert BaseComponent not in _resolve_provenance(FancyCard).values()
        assert BaseComponent not in _resolve_provenance(Card).values()

    def test_it_records_the_ancestor_that_supplied_each_kind(self, mro_dir):
        """All three kinds happen to live on the same ancestor here; each was
        still found by its own walk. Same terminal-slot caveat as above: the
        template's owner must not be the walk's unprobed last ancestor."""

        class Base(BaseComponent):
            pass

        class Card(Base):
            pass

        class FancyCard(Card):
            pass

        Base.__module__ = _MRO_MODULE
        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.css").write_text(".card {}")
        (mro_dir / "card.js").write_text("//card")

        assert _resolve_provenance(FancyCard) == {
            "template": Card,
            "css": Card,
            "js": Card,
        }

    def test_each_kind_names_its_own_ancestor(self, mro_dir):
        class Base(BaseComponent):
            pass

        class Card(Base):
            pass

        class FancyCard(Card):
            pass

        Base.__module__ = _MRO_MODULE
        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.js").write_text("//card")
        (mro_dir / "fancy_card.css").write_text(".fancy {}")

        assert _resolve_provenance(FancyCard) == {
            "template": Card,
            "css": FancyCard,
            "js": Card,
        }

    def test_a_kind_that_resolved_to_nothing_is_absent(self, mro_dir):
        class Base(BaseComponent):
            pass

        class Card(Base):
            pass

        class FancyCard(Card):
            pass

        Base.__module__ = _MRO_MODULE
        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")

        provenance = _resolve_provenance(FancyCard)

        assert provenance == {"css": Card}
        assert "js" not in provenance
        assert "template" not in provenance

    def test_an_asset_on_the_last_ancestor_is_still_named(self, mro_dir):
        """The template walk leaves its last ancestor unprobed and so cannot
        name it. The asset walk probes it, so it can."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_provenance(FancyCard) == {"css": Card}


class TestProvenanceProbeBudget:
    """ADR 0007's budget survives provenance: at most one `is_file` per
    ancestor per kind, and building a whole descriptor walks each kind once —
    not once for the path and again for the owner. The template walk's final
    fallback is unprobed by the walk itself, but registration's missing-template
    guard confirms it once to decide whether to raise."""

    @staticmethod
    def _count_is_file(monkeypatch) -> list[Path]:
        probed: list[Path] = []
        real_is_file = Path.is_file

        def counting(self, *args, **kwargs):
            probed.append(self)
            return real_is_file(self, *args, **kwargs)

        monkeypatch.setattr(Path, "is_file", counting)
        return probed

    def test_provenance_probes_each_ancestor_once_per_kind(self, mro_dir, monkeypatch):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")
        probed = self._count_is_file(monkeypatch)

        _resolve_provenance(VeryFancyCard)

        assert probed == [
            mro_dir / "very_fancy_card.pjx",
            mro_dir / "fancy_card.pjx",
            mro_dir / "very_fancy_card.css",
            mro_dir / "fancy_card.css",
            mro_dir / "card.css",
            mro_dir / "very_fancy_card.js",
            mro_dir / "fancy_card.js",
            mro_dir / "card.js",
        ]
        assert len(probed) == len(set(probed))

    def test_building_a_descriptor_probes_no_path_twice(self, mro_dir, monkeypatch):
        """Path and owner come out of one shared walk per kind, so a full
        descriptor build never asks the filesystem the same question twice."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")
        (mro_dir / "card.css").write_text(".card {}")
        probed = self._count_is_file(monkeypatch)

        descriptor = _resolve_class_descriptor(VeryFancyCard)

        assert descriptor.template_path == mro_dir / "fancy_card.pjx"
        assert descriptor.css_paths == (mro_dir / "card.css",)
        assert descriptor.js_paths == ()
        assert descriptor.provenance == {"template": FancyCard, "css": Card}
        assert probed == list(dict.fromkeys(probed))

    def test_a_direct_subclasss_descriptor_probes_only_its_asset_and_its_own_template(
        self, monkeypatch
    ):
        """One ancestor, so the template candidate is the unprobed terminal — the
        walk itself never probes it. But that terminal is exactly the candidate
        the missing-template guard confirms before deciding not to raise, so it
        picks up the one probe the walk skipped; the two optional asset
        candidates are unaffected.

        `Card` is defined before the spy is installed: `__pydantic_init_subclass__`
        already ran `_resolve_class_descriptor` once for its own registration, so
        a spy installed earlier would double every probe (registration's pass
        plus this test's explicit call)."""

        class Card(BaseComponent):
            pass

        probed = self._count_is_file(monkeypatch)

        _resolve_class_descriptor(Card)

        here = Path(__file__).parent

        assert probed == [here / "card.pjx", here / "card.css", here / "card.js"]


class TestAssetMroWalk:
    """ADR 0010, asset half: css and js each get their own nearest-ancestor
    walk. Assets are optional, so unlike the template walk every ancestor is
    probed and "nowhere in the MRO" is an empty result, not a guessed path."""

    def test_an_own_css_wins_over_an_ancestors(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")
        (mro_dir / "fancy_card.css").write_text(".fancy {}")

        css_paths, js_paths = _resolve_asset_paths(FancyCard)

        assert css_paths == (mro_dir / "fancy_card.css",)
        assert js_paths == ()

    def test_a_parents_css_is_used_when_the_child_has_none(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_asset_paths(FancyCard)[0] == (mro_dir / "card.css",)

    def test_a_parents_js_is_used_when_the_child_has_none(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.js").write_text("//card")

        assert _resolve_asset_paths(FancyCard)[1] == (mro_dir / "card.js",)

    def test_the_walk_hops_over_an_ancestor_with_no_file(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_asset_paths(VeryFancyCard)[0] == (mro_dir / "card.css",)

    def test_the_last_ancestor_is_probed_not_assumed(self, mro_dir):
        """The one place the asset walk deliberately diverges from the template
        walk: the template walk returns the root candidate unprobed, so it
        always yields a path. An asset must actually be on disk to be claimed."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_asset_paths(FancyCard)[0] == (mro_dir / "card.css",)

    def test_nothing_anywhere_is_an_empty_result_not_an_error(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        assert _resolve_asset_paths(FancyCard) == ((), ())

    def test_css_and_js_resolve_to_different_ancestors(self, mro_dir):
        """The kinds do not share a walk or short-circuit each other: the js
        winner is two levels up while the css winner is one."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.js").write_text("//card")
        (mro_dir / "fancy_card.css").write_text(".fancy {}")

        css_paths, js_paths = _resolve_asset_paths(VeryFancyCard)

        assert css_paths == (mro_dir / "fancy_card.css",)
        assert js_paths == (mro_dir / "card.js",)

    def test_siblings_resolve_independently_to_the_same_parent(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class PlainCard(Card):
            pass

        for klass in (Card, FancyCard, PlainCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_asset_paths(FancyCard)[0] == (mro_dir / "card.css",)
        assert _resolve_asset_paths(PlainCard)[0] == (mro_dir / "card.css",)


class TestPerKindIndependence:
    """ADR 0010: template, css and js resolve through three separate walks.
    Resolving one kind from an ancestor must never drag another kind along."""

    def test_inheriting_a_template_does_not_inherit_an_unrelated_asset(self, mro_dir):
        """The parent lends its template. Its css belongs to a *differently
        named* class, so nothing in the child's css walk matches and css stays
        empty — template inheritance did not pull an asset in behind it."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "unrelated.css").write_text(".unrelated {}")

        assert _resolve_template_path(FancyCard) == mro_dir / "card.pjx"
        assert _resolve_asset_paths(FancyCard) == ((), ())

    def test_a_co_located_asset_resolves_on_its_own_merits(self, mro_dir):
        """The other half of the distinction: when the ancestor's own
        `card.css` exists, the child gets it — because the css walk found it,
        not because the template walk landed on the same ancestor."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_template_path(FancyCard) == mro_dir / "card.pjx"
        assert _resolve_asset_paths(FancyCard)[0] == (mro_dir / "card.css",)

    def test_an_own_asset_survives_an_inherited_template(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "fancy_card.css").write_text(".fancy {}")

        assert _resolve_template_path(FancyCard) == mro_dir / "card.pjx"
        assert _resolve_asset_paths(FancyCard)[0] == (mro_dir / "fancy_card.css",)

    def test_an_own_template_does_not_block_an_inherited_asset(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "fancy_card.pjx").write_text("<div>fancy</div>")
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_template_path(FancyCard) == mro_dir / "fancy_card.pjx"
        assert _resolve_asset_paths(FancyCard)[0] == (mro_dir / "card.css",)


class TestMissingTemplateError:
    """A component must have a template. When no ancestor's candidate exists,
    registration fails on the spot instead of handing back a descriptor whose
    `template_path` points at nothing."""

    def test_defining_a_class_with_no_template_raises(self, mro_dir):
        with pytest.raises(TemplateNotFoundError):

            class Ghost(BaseComponent):
                __module__ = _MRO_MODULE

    def test_it_raises_while_the_class_body_runs_not_at_render(self, mro_dir):
        """Invariant 5: the class statement alone triggers it. Nothing is
        instantiated and nothing is rendered, and the class never becomes a
        usable name — the `NameError` proves the statement did not complete."""

        with pytest.raises(TemplateNotFoundError):

            class Ghost(BaseComponent):
                __module__ = _MRO_MODULE

        with pytest.raises(NameError):
            Ghost  # noqa: B018

    def test_the_message_lists_every_ancestor_and_its_candidate(self, mro_dir):
        """One entry per MRO level, nearest first — the whole chain the walk
        considered, not just where it landed. `Base` and `Middle` register
        against this test directory (stub templates), then get re-pointed so the
        chain resolves into the empty fixture directory."""

        class Base(BaseComponent):
            pass

        class Middle(Base):
            pass

        Base.__module__ = _MRO_MODULE
        Middle.__module__ = _MRO_MODULE

        with pytest.raises(TemplateNotFoundError) as excinfo:

            class Leaf(Middle):
                __module__ = _MRO_MODULE

        message = str(excinfo.value)
        assert "Leaf" in message
        assert "Middle" in message
        assert "Base" in message
        assert str(mro_dir / "leaf.pjx") in message
        assert str(mro_dir / "middle.pjx") in message
        assert str(mro_dir / "base.pjx") in message

    def test_the_message_names_the_class_being_defined(self, mro_dir):
        with pytest.raises(TemplateNotFoundError, match="Ghost has no template"):

            class Ghost(BaseComponent):
                __module__ = _MRO_MODULE

    def test_an_existing_fallback_registers_cleanly(self, mro_dir):
        """The success path is untouched: the fallback file exists, so the
        descriptor is built — and provenance stays empty, because confirming a
        fallback is not the same as the walk proving an owner."""
        (mro_dir / "solo.pjx").write_text("<div></div>", encoding="utf-8")

        class Solo(BaseComponent):
            __module__ = _MRO_MODULE

        assert Solo._pjx_descriptor.template_path == mro_dir / "solo.pjx"
        assert Solo._pjx_descriptor.provenance == {}

    def test_a_probed_winner_is_not_probed_twice(self, monkeypatch, mro_dir):
        """When the walk already proved an owner there is nothing to confirm, so
        the guard must not run: exactly one `is_file` per template candidate, and
        none after the winner."""

        class Base(BaseComponent):
            pass

        class Middle(Base):
            pass

        Base.__module__ = _MRO_MODULE
        Middle.__module__ = _MRO_MODULE
        (mro_dir / "middle.pjx").write_text("<div></div>", encoding="utf-8")

        probes: list[Path] = []
        real_is_file = Path.is_file

        def counting(self, *args, **kwargs):
            probes.append(self)
            return real_is_file(self, *args, **kwargs)

        monkeypatch.setattr(Path, "is_file", counting)

        class Leaf(Middle):
            __module__ = _MRO_MODULE

        assert [p for p in probes if p.suffix == ".pjx"] == [
            mro_dir / "leaf.pjx",
            mro_dir / "middle.pjx",
        ]

