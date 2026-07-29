import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

import pyjinhx2.component
from pyjinhx2.component import (
    BaseComponent,
    _defining_module_dir,
    _pascal_to_snake,
    _resolution_ancestors,
    _resolve_asset_paths,
    _resolve_class_descriptor,
    _resolve_provenance,
    _resolve_strict,
    _resolve_template_path,
    _walk_template,
)
from pyjinhx2.descriptor import ClassDescriptor


class TestResolveClassDescriptor:
    """The seam #272-#276 land behind: one call, one whole ClassDescriptor."""

    def test_returns_a_fully_constructed_descriptor(self):
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
        """The pinned zero-probe property from #272, restated for `is_file`:
        for `[cls]` the only ancestor is also the last one."""
        probed = self._count_is_file(monkeypatch)

        class Card(BaseComponent):
            pass

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
    free provenance for error messages and the dependency graph. Template kind
    only; css/js stay absent until #276 gives assets real resolution."""

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

    def test_it_never_records_css_or_js_kinds(self, mro_dir):
        """Per-kind independence at the resolver level: assets are still #276's
        stub, so provenance must not invent owners for kinds nothing resolved.
        Same terminal-slot caveat as the other tests above."""

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

        provenance = _resolve_provenance(FancyCard)

        assert provenance == {"template": Card}
        assert "css" not in provenance
        assert "js" not in provenance


class TestPerKindIndependence:
    """ADR 0010: template and assets resolve through separate walks. #273 gave
    template one; css/js keep the stub until #276. If this test starts failing
    because `_resolve_asset_paths` grew behavior, that behavior belongs in #276
    with its own tests — not smuggled in through the template walk."""

    def test_asset_resolution_is_still_the_untouched_stub(self):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        assert _resolve_asset_paths(Card) == ((), ())
        assert _resolve_asset_paths(FancyCard) == ((), ())

    def test_inheriting_a_template_does_not_inherit_assets(self, mro_dir):
        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.css").write_text(".card {}")

        assert _resolve_template_path(FancyCard) == mro_dir / "card.pjx"
        assert _resolve_asset_paths(FancyCard) == ((), ())
