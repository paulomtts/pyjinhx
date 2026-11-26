"""Tests for template path resolution and the template MRO walk."""

import sys
import types
from pathlib import Path

import pytest

import pyjinhx.components.base
from pyjinhx.components.base import (
    BaseComponent,
    _asset_candidate,
    _defining_module_dir,
    _pascal_to_snake,
    _resolution_ancestors,
    _resolve_template_path,
    _template_candidate,
    _walk_template,
)
from tests.unit.components.base._class_descriptor_helpers import _MRO_MODULE


class TestPascalToSnake:
    """The ADR 0007 filename convention: acronym-aware PascalCase -> snake_case,
    matching v0.x's pyjinhx/utils.py:pascal_case_to_snake_case exactly, but
    reimplemented locally because pyjinhx must not import the legacy package."""

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

    def test_it_uses_the_snake_case_class_name_and_the_kind_extension(self):
        class FancyCard(BaseComponent):
            pass

        here = Path(__file__).parent

        assert _asset_candidate(FancyCard, "css") == here / "fancy_card.css"
        assert _asset_candidate(FancyCard, "js") == here / "fancy_card.js"

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
        module = types.ModuleType("pyjinhx_test_fileless_template_module")
        sys.modules["pyjinhx_test_fileless_template_module"] = module
        try:

            class Card(BaseComponent):
                pass

            Card.__module__ = "pyjinhx_test_fileless_template_module"
            with pytest.raises(NotImplementedError, match="no file on disk"):
                _resolve_template_path(Card)
        finally:
            del sys.modules["pyjinhx_test_fileless_template_module"]

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


class TestWalkInlineTemplate:
    """A class whose own body assigns ``template`` owns its template: the walk
    answers with its module file before probing for a ``.pjx``.

    Each test names its classes differently: an inline template is found in
    the module source by class name, so two same-named classes with a
    template in one file are refused."""

    def test_an_inline_template_wins_over_an_adjacent_file(self, mro_dir):
        class Tile(BaseComponent):
            template = "<div>inline</div>"

        Tile.__module__ = _MRO_MODULE
        (mro_dir / "tile.pjx").write_text("<div>file</div>")

        assert _walk_template(Tile) == (mro_dir / f"{_MRO_MODULE}.py", Tile)

    def test_a_subclass_file_overrides_a_parents_inline_template(self, mro_dir):
        class Panel(BaseComponent):
            template = "<div>inline</div>"

        class FancyPanel(Panel):
            pass

        Panel.__module__ = _MRO_MODULE
        FancyPanel.__module__ = _MRO_MODULE
        (mro_dir / "fancy_panel.pjx").write_text("<div>fancy</div>")

        assert _walk_template(FancyPanel) == (mro_dir / "fancy_panel.pjx", FancyPanel)

    def test_an_inline_owner_costs_no_probe(self, mro_dir, monkeypatch):
        class Sheet(BaseComponent):
            template = "<div>inline</div>"

        class FancySheet(Sheet):
            pass

        Sheet.__module__ = _MRO_MODULE
        FancySheet.__module__ = _MRO_MODULE
        probed = TestTemplateWalkProbeBudget._count_is_file(monkeypatch)

        _walk_template(Sheet)
        _walk_template(FancySheet)

        assert probed == [mro_dir / "fancy_sheet.pjx"]


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
        real = pyjinhx.components.base._defining_module_dir

        def spying(cls):
            considered.append(cls)
            return real(cls)

        monkeypatch.setattr(pyjinhx.components.base, "_defining_module_dir", spying)

        _resolve_template_path(FancyCard)

        assert BaseComponent not in considered
        assert considered == [FancyCard, Card]
