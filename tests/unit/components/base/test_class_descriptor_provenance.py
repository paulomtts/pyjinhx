"""Tests for the provenance of resolved templates and their probe budget."""

from pathlib import Path

from pyjinhx.components.base import (
    BaseComponent,
    _resolve_class_descriptor,
    _resolve_provenance,
)
from tests.unit.components.base._class_descriptor_helpers import _MRO_MODULE


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
    ancestor per kind, none for the template walk's final fallback, and
    building a whole descriptor walks each kind once — not once for the path
    and again for the owner."""

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

    def test_a_direct_subclasss_descriptor_probes_only_its_assets(self, monkeypatch):
        """One ancestor, so the template candidate is the unprobed terminal and
        the only probes left are the two optional asset candidates.

        `Card` is defined before the spy is installed: `__pydantic_init_subclass__`
        already ran `_resolve_class_descriptor` once for its own registration, so
        a spy installed earlier would double every probe (registration's pass
        plus this test's explicit call)."""

        class Card(BaseComponent):
            pass

        probed = self._count_is_file(monkeypatch)

        _resolve_class_descriptor(Card)

        here = Path(__file__).parent

        assert probed == [here / "card.css", here / "card.js"]
