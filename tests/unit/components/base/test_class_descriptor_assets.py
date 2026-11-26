"""Tests for the asset MRO walk, per-kind independence and the descriptor inheritance matrix."""

from pathlib import Path

from pyjinhx.components.base import (
    BaseComponent,
    _missing_template_error,
    _resolve_asset_paths,
    _resolve_class_descriptor,
    _resolve_provenance,
    _resolve_template_path,
    rebuild_class_descriptor,
)
from tests.unit.components.base._class_descriptor_helpers import _MRO_MODULE


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
    """The diagnostic a caller raises when no ancestor has a template file.
    Returned, not raised: the raise site belongs to the renderer."""

    def test_it_returns_a_lookup_error_instead_of_raising(self):
        class Card(BaseComponent):
            pass

        error = _missing_template_error(Card)

        assert isinstance(error, LookupError)

    def test_a_bare_class_message_names_the_class_and_its_one_candidate(self):
        class Card(BaseComponent):
            pass

        message = str(_missing_template_error(Card))

        assert "Card" in message
        assert str(Path(__file__).parent / "card.pjx") in message

    def test_a_chain_lists_every_ancestors_candidate_nearest_first(self, mro_dir):
        class Grandparent(BaseComponent):
            pass

        class Parent(Grandparent):
            pass

        class Child(Parent):
            pass

        for klass in (Grandparent, Parent, Child):
            klass.__module__ = _MRO_MODULE

        message = str(_missing_template_error(Child))

        assert str(mro_dir / "child.pjx") in message
        assert str(mro_dir / "parent.pjx") in message
        assert str(mro_dir / "grandparent.pjx") in message
        assert message.index("child.pjx") < message.index("parent.pjx")
        assert message.index("parent.pjx") < message.index("grandparent.pjx")

    def test_each_listed_line_pairs_an_ancestor_name_with_its_path(self, mro_dir):
        """The point of the message: a subclass author can read off which class
        was expected to own which file, not just that something is missing."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        message = str(_missing_template_error(FancyCard))

        assert f"FancyCard -> {mro_dir / 'fancy_card.pjx'}" in message
        assert f"Card -> {mro_dir / 'card.pjx'}" in message
        assert "FancyCard" in message.splitlines()[0]

    def test_the_message_states_plainly_that_no_ancestor_has_a_file(self):
        class Card(BaseComponent):
            pass

        message = str(_missing_template_error(Card))

        assert "no class it inherits from has a .pjx file" in message

    def test_the_message_labels_the_probed_paths(self):
        class Card(BaseComponent):
            pass

        message = str(_missing_template_error(Card))

        assert "Paths probed, nearest first:" in message

    def test_it_performs_no_filesystem_probes(self, mro_dir, monkeypatch):
        """The builder is pure path arithmetic: the walk that already answered
        `_resolve_template_path` spent the filesystem budget (ADR 0007); this
        formatter must not spend any more, not even for the last ancestor.

        Classes are defined and re-pointed at `mro_dir` *before* the spy is
        installed: `__pydantic_init_subclass__` itself walks template and
        asset candidates at class-definition time (against whatever module the
        class has *then*), and installing the spy first would let those
        registration-time probes (against the test file's own directory, since
        `__module__` isn't reassigned yet) leak into the assertion below — the
        same reason `TestTemplateWalkProbeBudget` defines its classes first."""

        class Grandparent(BaseComponent):
            pass

        class Parent(Grandparent):
            pass

        class Child(Parent):
            pass

        for klass in (Grandparent, Parent, Child):
            klass.__module__ = _MRO_MODULE

        probed: list[Path] = []
        real_is_file = Path.is_file
        real_exists = Path.exists

        def counting_is_file(self: Path, *args, **kwargs):
            probed.append(self)
            return real_is_file(self, *args, **kwargs)

        def counting_exists(self: Path, *args, **kwargs):
            probed.append(self)
            return real_exists(self, *args, **kwargs)

        monkeypatch.setattr(Path, "is_file", counting_is_file)
        monkeypatch.setattr(Path, "exists", counting_exists)

        assert isinstance(_missing_template_error(Child), LookupError)
        assert probed == []

    def test_the_resolvers_still_succeed_for_a_template_less_class(self, mro_dir):
        """The error exists as a value only. Registration and resolution must
        keep answering with the unprobed fallback for a class with no file, so
        no resolver has quietly started raising it."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        Card.__module__ = _MRO_MODULE
        FancyCard.__module__ = _MRO_MODULE

        rebuild_class_descriptor(FancyCard)

        assert _resolve_template_path(FancyCard) == mro_dir / "card.pjx"
        assert _resolve_provenance(FancyCard) == {}
        assert FancyCard.__pjx_descriptor__.template_path == mro_dir / "card.pjx"


class TestDescriptorInheritanceMatrix:
    """One `_resolve_class_descriptor` call, every field checked together.

    The rest of this file checks one resolver at a time; nothing checks that
    the three independent walks land in the *same* descriptor consistently —
    that the path a kind resolved to and the ancestor `provenance` credits for
    it always agree, even when the three kinds come from three different
    ancestors.

    Every chain here carries a `Widget` tail that owns no files. The template
    walk returns the last ancestor's candidate unprobed, so an unproven
    ancestor can never be named in provenance; the tail absorbs that slot and
    lets the class that really owns the template be probed and credited.
    """

    def test_own_files_are_named_as_their_own_provenance(self, mro_dir):
        """The base case the mixed scenarios are read against: when one class
        owns all three files, every path is its own and it is credited for
        every kind."""

        class Widget(BaseComponent):
            pass

        class Card(Widget):
            pass

        for klass in (Widget, Card):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.css").write_text(".card {}")
        (mro_dir / "card.js").write_text("//card")

        descriptor = _resolve_class_descriptor(Card)

        assert descriptor.template_path == mro_dir / "card.pjx"
        assert descriptor.css_paths == (mro_dir / "card.css",)
        assert descriptor.js_paths == (mro_dir / "card.js",)
        assert descriptor.provenance == {"template": Card, "css": Card, "js": Card}

    def test_all_kinds_inherited_from_the_same_ancestor(self, mro_dir):
        """A leaf with nothing of its own gets the parent's three files and
        credits the parent for all three — the descriptor must not silently
        credit the class it was built for."""

        class Widget(BaseComponent):
            pass

        class Card(Widget):
            pass

        class FancyCard(Card):
            pass

        for klass in (Widget, Card, FancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.css").write_text(".card {}")
        (mro_dir / "card.js").write_text("//card")

        descriptor = _resolve_class_descriptor(FancyCard)

        assert descriptor.template_path == mro_dir / "card.pjx"
        assert descriptor.css_paths == (mro_dir / "card.css",)
        assert descriptor.js_paths == (mro_dir / "card.js",)
        assert descriptor.provenance == {"template": Card, "css": Card, "js": Card}

    def test_all_kinds_inherited_from_a_grandparent_through_an_empty_parent(
        self, mro_dir
    ):
        """An intermediate class that contributes nothing must be transparent
        to all three walks at once: the descriptor names the grandparent for
        every kind, never the empty class standing between."""

        class Widget(BaseComponent):
            pass

        class Card(Widget):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Widget, Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.css").write_text(".card {}")
        (mro_dir / "card.js").write_text("//card")

        descriptor = _resolve_class_descriptor(VeryFancyCard)

        assert descriptor.template_path == mro_dir / "card.pjx"
        assert descriptor.css_paths == (mro_dir / "card.css",)
        assert descriptor.js_paths == (mro_dir / "card.js",)
        assert descriptor.provenance == {"template": Card, "css": Card, "js": Card}

    def test_mixed_provenance_across_three_ancestors(self, mro_dir):
        """The case no single-resolver test can catch: three kinds resolving to
        three different ancestors in one MRO. Each path field and its
        provenance entry must agree pairwise, with no walk borrowing another's
        winner."""

        class Widget(BaseComponent):
            pass

        class Card(Widget):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Widget, Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "fancy_card.css").write_text(".fancy {}")
        (mro_dir / "very_fancy_card.js").write_text("//very")

        descriptor = _resolve_class_descriptor(VeryFancyCard)

        assert descriptor.template_path == mro_dir / "card.pjx"
        assert descriptor.css_paths == (mro_dir / "fancy_card.css",)
        assert descriptor.js_paths == (mro_dir / "very_fancy_card.js",)
        assert descriptor.provenance == {
            "template": Card,
            "css": FancyCard,
            "js": VeryFancyCard,
        }

    def test_mixed_provenance_with_one_kind_resolved_to_none(self, mro_dir):
        """An absent kind is an absent *key*, not a key mapped to None or to
        whichever ancestor happened to win another kind. Asserted next to two
        resolved kinds so a leak into the empty slot would show up."""

        class Widget(BaseComponent):
            pass

        class Card(Widget):
            pass

        class FancyCard(Card):
            pass

        for klass in (Widget, Card, FancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "card.css").write_text(".card {}")

        descriptor = _resolve_class_descriptor(FancyCard)

        assert descriptor.template_path == mro_dir / "card.pjx"
        assert descriptor.css_paths == (mro_dir / "card.css",)
        assert descriptor.js_paths == ()
        assert "js" not in descriptor.provenance
        assert descriptor.provenance == {"template": Card, "css": Card}

    def test_siblings_with_a_shared_ancestor_get_independent_mixed_descriptors(
        self, mro_dir
    ):
        """Two subclasses of one parent, each owning a different kind. Both
        descriptors are built from the same directory, so a shared or leaked
        result would show up as one sibling claiming the other's file."""

        class Widget(BaseComponent):
            pass

        class Card(Widget):
            pass

        class FancyCard(Card):
            pass

        class PlainCard(Card):
            pass

        for klass in (Widget, Card, FancyCard, PlainCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.pjx").write_text("<div>card</div>")
        (mro_dir / "fancy_card.css").write_text(".fancy {}")
        (mro_dir / "plain_card.js").write_text("//plain")

        fancy = _resolve_class_descriptor(FancyCard)
        plain = _resolve_class_descriptor(PlainCard)

        assert fancy.template_path == mro_dir / "card.pjx"
        assert fancy.css_paths == (mro_dir / "fancy_card.css",)
        assert fancy.js_paths == ()
        assert fancy.provenance == {"template": Card, "css": FancyCard}

        assert plain.template_path == mro_dir / "card.pjx"
        assert plain.css_paths == ()
        assert plain.js_paths == (mro_dir / "plain_card.js",)
        assert plain.provenance == {"template": Card, "js": PlainCard}

    def test_missing_template_error_message_in_a_mixed_asset_chain(self, mro_dir):
        """The diagnostic is built from path arithmetic over the whole MRO, so
        it must stay complete and correctly paired even when the css and js
        walks *did* find owners in that same chain — a resolved asset must not
        stand in for, reorder or drop a template candidate."""

        class Card(BaseComponent):
            pass

        class FancyCard(Card):
            pass

        class VeryFancyCard(FancyCard):
            pass

        for klass in (Card, FancyCard, VeryFancyCard):
            klass.__module__ = _MRO_MODULE
        (mro_dir / "card.css").write_text(".card {}")
        (mro_dir / "fancy_card.js").write_text("//fancy")

        descriptor = _resolve_class_descriptor(VeryFancyCard)
        message = str(_missing_template_error(VeryFancyCard))

        assert descriptor.css_paths == (mro_dir / "card.css",)
        assert descriptor.js_paths == (mro_dir / "fancy_card.js",)
        assert descriptor.provenance == {"css": Card, "js": FancyCard}

        assert f"VeryFancyCard -> {mro_dir / 'very_fancy_card.pjx'}" in message
        assert f"FancyCard -> {mro_dir / 'fancy_card.pjx'}" in message
        assert f"Card -> {mro_dir / 'card.pjx'}" in message
        assert message.index("very_fancy_card.pjx") < message.index("fancy_card.pjx")
        assert message.index("fancy_card.pjx") < message.index("card.pjx")
        assert ".css" not in message
        assert ".js" not in message
