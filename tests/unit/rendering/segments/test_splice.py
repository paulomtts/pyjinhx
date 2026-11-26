"""Tests for single-root enforcement, splicing and serialization of segments."""

import ast
import inspect

import pytest

import pyjinhx.rendering.segments
from pyjinhx.rendering.segments import (
    ChildRef,
    RenderedLevel,
    VerbatimParser,
    serialize,
    splice,
)
from tests.unit.rendering.segments._segments_helpers import make_child_ref, make_level


def parsed_level(markup: str) -> "RenderedLevel":
    """A RenderedLevel whose root_span came from a real parse, not a hand-written
    tuple — the whole point of TestSpliceRootSpanCorrectness below."""
    parser = VerbatimParser()
    parser.feed(markup)
    parser.close()
    assert parser.root_span is not None, f"fixture has no tag event: {markup!r}"
    segments: list[str | ChildRef | RenderedLevel] = list(parser.segments)
    return RenderedLevel(segments=segments, root_span=parser.root_span, descriptor=None)


class TestEnforceSingleRoot:
    @staticmethod
    def parsed(markup: str) -> "VerbatimParser":
        parser = VerbatimParser()
        parser.feed(markup)
        parser.close()
        return parser

    @pytest.mark.parametrize(
        "markup",
        [
            "<div>hi</div>",
            "<div><p>a</p><p>b</p></div>",
            '<PJXIcon name="gear"/>',
            '<PJXButton label="Go">text</PJXButton>',
            "<PJXAccordion><PJXIcon name='gear'/></PJXAccordion>",
            "<div>\n  <PJXButton label='Save'/>\n  <p>hi</p>\n</div>",
        ],
    )
    def test_single_root_does_not_raise(self, markup: str):
        assert self.parsed(markup).enforce_single_root() is None

    def test_two_plain_siblings_raise_naming_the_extra_markup(self):
        parser = self.parsed("<p>a</p><p>b</p>")
        with pytest.raises(ValueError) as excinfo:
            parser.enforce_single_root()
        assert "<p>" in str(excinfo.value)

    def test_two_custom_siblings_raise_naming_the_extra_markup(self):
        parser = self.parsed('<PJXButton label="Go"/> and <PJXIcon name="gear"/>')
        with pytest.raises(ValueError) as excinfo:
            parser.enforce_single_root()
        assert '<PJXIcon name="gear"/>' in str(excinfo.value)

    def test_three_siblings_report_every_extra_root(self):
        parser = self.parsed("<p>a</p><span>b</span><b>c</b>")
        with pytest.raises(ValueError) as excinfo:
            parser.enforce_single_root()
        message = str(excinfo.value)
        assert "<span>" in message
        assert "<b>" in message

    def test_zero_roots_raise_naming_the_markup(self):
        parser = self.parsed("plain text, no markup at all")
        assert parser.root_span is None
        with pytest.raises(ValueError) as excinfo:
            parser.enforce_single_root()
        assert "plain text, no markup at all" in str(excinfo.value)

    def test_unclosed_root_tag_at_eof_is_still_one_root(self):
        assert self.parsed("<PJXButton>go").enforce_single_root() is None
        assert self.parsed("<div><p>hi").enforce_single_root() is None

    @pytest.mark.parametrize(
        "markup",
        [
            '<img src="x.png"/>',
            '<img src="x.png">',
            "<br>",
            "<input disabled value=bare>",
        ],
    )
    def test_void_element_as_sole_root_does_not_raise(self, markup: str):
        assert self.parsed(markup).enforce_single_root() is None

    @pytest.mark.parametrize(
        "markup",
        [
            '<img src="a"/><img src="b"/>',
            '<img src="a"><img src="b">',
            '<img src="a"><p>b</p>',
            "<br><br>",
        ],
    )
    def test_void_elements_still_count_as_separate_roots(self, markup: str):
        with pytest.raises(ValueError):
            self.parsed(markup).enforce_single_root()

    def test_void_element_inside_a_single_root_does_not_trip_the_counter(self):
        markup = '<div><img src="a"><br>text<hr></div>'
        assert self.parsed(markup).enforce_single_root() is None

    def test_leading_stray_close_tag_does_not_hide_a_multi_root_violation(self):
        # `</span>` closes nothing; the two <p> siblings are still two roots.
        with pytest.raises(ValueError):
            self.parsed("</span><p>a</p><p>b</p>").enforce_single_root()

    def test_leading_stray_close_tag_leaves_a_single_root_valid(self):
        assert self.parsed("</span><div>hi</div>").enforce_single_root() is None

    def test_mismatched_close_tag_does_not_reopen_the_top_level(self):
        # `</span>` inside <div> matches no open element, so <p> is still nested.
        assert self.parsed("<div></span><p>a</p></div>").enforce_single_root() is None

    def test_close_tag_for_an_ancestor_closes_the_levels_below_it(self):
        # `</div>` closes both <p> and <div>, so the trailing <p> is a second root.
        with pytest.raises(ValueError):
            self.parsed("<div><p>hi</div><p>x</p>").enforce_single_root()

    def test_nested_custom_tags_do_not_trip_the_counter(self):
        markup = "<PJXAccordion><PJXPanel></PJXPanel><PJXIcon name='a'/></PJXAccordion>"
        assert self.parsed(markup).enforce_single_root() is None

    @pytest.mark.parametrize(
        "markup",
        [
            "",
            "plain text, no markup at all",
            "&amp; just an entity",
            "<p>a</p><p>b</p>",
            '<img src="a"/><img src="b"/>',
            "</span>hi",
            "<PJXAccordion><PJXIcon name='gear'/>",
        ],
    )
    def test_parsing_alone_never_raises(self, markup: str):
        # Enforcement is opt-in: feed()/close() must stay validation-free so every
        # round-trip and root_span test can parse malformed markup unharmed.
        parser = VerbatimParser()
        parser.feed(markup)
        parser.close()
        assert isinstance(parser.segments, list)

    def test_enforce_is_not_called_from_feed_or_close(self):
        # AST-based, not a source-text split: `enforce_single_root` is defined
        # *before* handle_starttag/handle_startendtag/handle_endtag in the file
        # (Step 5 inserts it right after `_record_root_span`), so a naive
        # `source.split("def enforce_single_root", 1)[0]` check only inspects
        # __init__/feed/_raw_at/_record_root_span/_count_root_candidate — it
        # would silently miss a call added inside any handle_* method, which is
        # exactly the case this guard exists to catch. Walk every method of the
        # class instead (skipping enforce_single_root's own body) and assert
        # none of them calls it.
        tree = ast.parse(inspect.getsource(VerbatimParser))
        (cls,) = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        for method in cls.body:
            if not isinstance(method, ast.FunctionDef):
                continue
            if method.name == "enforce_single_root":
                continue
            for node in ast.walk(method):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else getattr(func, "id", None)
                )
                assert name != "enforce_single_root", (
                    f"{method.name} must not call enforce_single_root()"
                )

    def test_enforcement_path_never_swallows(self):
        # Invariant 3 / ADR 0002: single-root violations raise unconditionally.
        source = inspect.getsource(pyjinhx.rendering.segments)
        assert "except" not in source


class TestSplice:
    def test_inserts_text_at_offset(self):
        level = make_level(segments=['<div class="card">hi</div>'], root_span=(0, 18))
        splice(level, 17, ' data-x="1"')
        assert level.segments[0] == '<div class="card" data-x="1">hi</div>'

    def test_root_span_end_shifts_by_inserted_length(self):
        level = make_level(segments=['<div class="card">hi</div>'], root_span=(0, 18))
        splice(level, level.root_span[1] - 1, ' data-x="1"')
        assert level.root_span == (0, 29)

    def test_returns_the_same_level_for_chaining(self):
        level = make_level(segments=['<div class="card">hi</div>'], root_span=(0, 18))
        assert splice(level, 17, ' data-x="1"') is level

    def test_second_splice_after_first_lands_correctly(self):
        # First splice = #247's root-attr stamp at render time.
        level = make_level(segments=['<div class="card">hi</div>'], root_span=(0, 18))
        splice(level, level.root_span[1] - 1, ' data-x="1"')
        # Second splice = L3's OOB fan-out at response time, using the span the
        # first call left behind.
        splice(level, level.root_span[1] - 1, ' hx-swap-oob="true"')
        assert (
            level.segments[0]
            == '<div class="card" data-x="1" hx-swap-oob="true">hi</div>'
        )
        assert level.root_span == (0, 48)
        # The span still bounds exactly the root tag, closing `>` included.
        markup = level.segments[0]
        assert isinstance(markup, str)
        assert markup[level.root_span[0] : level.root_span[1]] == (
            '<div class="card" data-x="1" hx-swap-oob="true">'
        )

    def test_empty_text_is_a_no_op(self):
        level = make_level(segments=['<div class="card">hi</div>'], root_span=(0, 18))
        splice(level, 17, "")
        assert level.segments[0] == '<div class="card">hi</div>'
        assert level.root_span == (0, 18)

    def test_unicode_text_offsets_are_character_based(self):
        level = make_level(segments=['<div class="card">hi</div>'], root_span=(0, 18))
        text = ' data-emoji="\U0001f389é"'
        assert len(text) == 16  # code points, not the 20 bytes of its UTF-8 form
        splice(level, 17, text)
        markup = level.segments[0]
        assert isinstance(markup, str)
        assert markup == '<div class="card" data-emoji="\U0001f389é">hi</div>'
        assert level.root_span == (0, 34)
        assert len(markup) == 42

    @pytest.mark.parametrize(
        ("offset", "text", "expected_markup", "expected_span"),
        [
            (0, "X", 'X<div class="card">hi</div>', (1, 19)),
            (26, "Y", '<div class="card">hi</div>Y', (0, 18)),
        ],
        ids=["prepend", "append"],
    )
    def test_insert_at_start_and_at_end(
        self, offset, text, expected_markup, expected_span
    ):
        level = make_level(segments=['<div class="card">hi</div>'], root_span=(0, 18))
        markup = level.segments[0]
        assert isinstance(markup, str)
        assert offset in (0, len(markup))
        splice(level, offset, text)
        assert level.segments[0] == expected_markup
        assert level.root_span == expected_span

    @pytest.mark.parametrize(
        "root",
        [make_child_ref(), make_level()],
        ids=["child-ref", "nested-level"],
    )
    def test_raises_when_root_segment_is_not_a_str(self, root):
        level = make_level(segments=[root, "</div>"], root_span=(0, 18))
        with pytest.raises(AssertionError):
            splice(level, 17, ' data-x="1"')


class TestSpliceRootSpanCorrectness:
    """The stamp offset (`root_span[1] - 1`) lands just inside the root tag's
    closing `>` for every markup shape — with root_span recorded by a real
    VerbatimParser, not supplied by hand as every other TestSplice test does.
    """

    STAMP = ' data-x="1"'
    FAN_OUT = ' hx-swap-oob="true"'

    @pytest.mark.parametrize(
        ("markup", "open_tag"),
        [
            ("<div>hi</div>", "<div>"),
            ('<div class="card">hi</div>', '<div class="card">'),
            (
                '<div class="card" id="x" data-y="1">hi</div>',
                '<div class="card" id="x" data-y="1">',
            ),
            ('<DIV class="card">hi</DIV>', '<DIV class="card">'),
            (
                '<div\n  class="card"\n  id="x">hi</div>',
                '<div\n  class="card"\n  id="x">',
            ),
            # `<input type="text"/>`: the stamp lands before the `>` as specified,
            # which puts it after the `/` (`<input type="text"/ data-x="1">`).
            # root_span and splice are both correct here; deciding whether a
            # self-closing root should be stamped at all belongs to #247.
            ('<input type="text"/>', '<input type="text"/>'),
            ('<img src="x.png">', '<img src="x.png">'),
            (
                '<div title="héllo \U0001f389">hi</div>',
                '<div title="héllo \U0001f389">',
            ),
            ("<div hidden>hi</div>", "<div hidden>"),
        ],
        ids=[
            "no-attrs",
            "one-attr",
            "many-attrs",
            "upper-case-tag",
            "newlines-in-open-tag",
            "self-closing-void",
            "bare-void",
            "unicode-attr",
            "boolean-attr",
        ],
    )
    def test_first_splice_lands_before_the_closing_bracket(
        self, markup: str, open_tag: str
    ):
        level = parsed_level(markup)
        # The parse, not the test, decides where the root tag ends.
        assert level.root_span == (0, len(open_tag))
        original_first = level.segments[0]
        assert isinstance(original_first, str)
        splice(level, level.root_span[1] - 1, self.STAMP)
        first = level.segments[0]
        assert isinstance(first, str)
        # The stamp goes in just before the open tag's `>`; nothing after the open
        # tag inside segments[0] (void elements have no separate segments) moves.
        assert (
            first
            == original_first[: len(open_tag) - 1]
            + self.STAMP
            + original_first[len(open_tag) - 1 :]
        )
        assert level.root_span == (0, len(open_tag) + len(self.STAMP))
        assert first[level.root_span[0] : level.root_span[1]] == (
            open_tag[:-1] + self.STAMP + ">"
        )

    @pytest.mark.parametrize(
        ("markup", "open_tag"),
        [
            ("<div>hi</div>", "<div>"),
            ('<div class="card">hi</div>', '<div class="card">'),
            (
                '<div class="card" id="x" data-y="1">hi</div>',
                '<div class="card" id="x" data-y="1">',
            ),
            ('<DIV class="card">hi</DIV>', '<DIV class="card">'),
            (
                '<div\n  class="card"\n  id="x">hi</div>',
                '<div\n  class="card"\n  id="x">',
            ),
            # `<input type="text"/>`: the stamp lands before the `>` as specified,
            # which puts it after the `/` (`<input type="text"/ data-x="1">`).
            # root_span and splice are both correct here; deciding whether a
            # self-closing root should be stamped at all belongs to #247.
            ('<input type="text"/>', '<input type="text"/>'),
            ('<img src="x.png">', '<img src="x.png">'),
            (
                '<div title="héllo \U0001f389">hi</div>',
                '<div title="héllo \U0001f389">',
            ),
            ("<div hidden>hi</div>", "<div hidden>"),
        ],
        ids=[
            "no-attrs",
            "one-attr",
            "many-attrs",
            "upper-case-tag",
            "newlines-in-open-tag",
            "self-closing-void",
            "bare-void",
            "unicode-attr",
            "boolean-attr",
        ],
    )
    def test_second_splice_still_lands_before_the_closing_bracket(
        self, markup: str, open_tag: str
    ):
        # First splice = #247's root-attr stamp at render time; second = L3's OOB
        # fan-out at response time, reading the span the first call left behind
        # (architecture-overview.md §4: written twice, parsed never).
        level = parsed_level(markup)
        original_first = level.segments[0]
        assert isinstance(original_first, str)
        splice(level, level.root_span[1] - 1, self.STAMP)
        splice(level, level.root_span[1] - 1, self.FAN_OUT)
        first = level.segments[0]
        assert isinstance(first, str)
        expected_open = open_tag[:-1] + self.STAMP + self.FAN_OUT + ">"
        assert first == expected_open + original_first[len(open_tag) :]
        assert level.root_span == (0, len(expected_open))
        assert first[level.root_span[0] : level.root_span[1]] == expected_open


class TestSerialize:
    def test_joins_flat_string_segments_in_order(self):
        level = make_level(segments=["<div>", "hi", "</div>"])
        assert serialize(level) == "<div>hi</div>"

    def test_returns_a_str(self):
        level = make_level(segments=["<div>", "hi", "</div>"])
        assert type(serialize(level)) is str

    def test_single_string_segment_passes_through_verbatim(self):
        level = make_level(segments=['<div class="card">hi &amp; bye</div>'])
        assert serialize(level) == '<div class="card">hi &amp; bye</div>'

    def test_nested_level_is_spliced_in_at_its_position(self):
        child = make_level(segments=["<button>go</button>"])
        parent = make_level(segments=["<div>", child, "</div>"])
        assert serialize(parent) == "<div><button>go</button></div>"

    def test_only_a_nested_level_serializes_to_that_child(self):
        child = make_level(segments=["<button>go</button>"])
        parent = make_level(segments=[child])
        assert serialize(parent) == "<button>go</button>"

    def test_recurses_depth_two_and_deeper(self):
        grandchild = make_level(segments=["<i>", "deep", "</i>"])
        child = make_level(segments=["<span>", grandchild, "</span>"])
        parent = make_level(segments=["<div>", child, "</div>"])
        assert serialize(parent) == "<div><span><i>deep</i></span></div>"

    def test_multiple_sibling_levels_keep_their_order(self):
        first = make_level(segments=["<b>1</b>"])
        second = make_level(segments=["<b>2</b>"])
        parent = make_level(segments=["<div>", first, "|", second, "</div>"])
        assert serialize(parent) == "<div><b>1</b>|<b>2</b></div>"

    def test_empty_segments_serialize_to_empty_string(self):
        assert serialize(make_level(segments=[])) == ""

    def test_empty_nested_level_contributes_nothing(self):
        child = make_level(segments=[])
        parent = make_level(segments=["<div>", child, "</div>"])
        assert serialize(parent) == "<div></div>"

    def test_ignores_root_span(self):
        # serialize never reads root_span; a nonsense span changes nothing.
        level = make_level(segments=["<div>hi</div>"], root_span=(99, 999))
        assert serialize(level) == "<div>hi</div>"

    def test_raises_when_a_segment_is_a_live_child_ref(self):
        # Mirrors TestSplice.test_raises_when_root_segment_is_not_a_str:
        # an L1-expanded tree has no live ChildRef left by join time.
        level = make_level(segments=["<div>", make_child_ref(), "</div>"])
        with pytest.raises(AssertionError, match="ChildRef"):
            serialize(level)

    def test_raises_when_a_nested_level_holds_a_live_child_ref(self):
        child = make_level(segments=[make_child_ref()])
        parent = make_level(segments=["<div>", child, "</div>"])
        with pytest.raises(AssertionError, match="ChildRef"):
            serialize(parent)


class TestRoundTripThroughSerialize:
    """The composed pipeline: parse -> RenderedLevel -> serialize -> same string.

    Invariant 1 (architecture-overview.md §1, ADR 0002): pyjinhx never re-parses
    its own output, so a level's segments must carry the source text losslessly
    all the way to the single join. TestVerbatimParser.round_trip proves the cut
    is lossless at the parser boundary and TestSerialize proves the join is
    lossless over hand-built levels; this class is the only place a real string
    travels the whole way through both.

    Domain is markup *without* custom tags: no fixture here holds a PascalCase
    tag, so nothing is cut into a ChildRef and every segment stays a str.
    Adversarial markup is #261; root_span correctness is #262.
    """

    @staticmethod
    def round_trip(markup: str) -> str:
        parser = VerbatimParser()
        parser.feed(markup)
        parser.close()
        # No fixture in this class contains a PascalCase tag, so #254's cutting
        # never fires and every segment is raw source text. enforce_single_root
        # is deliberately not called: several fixtures are zero-root (plain text)
        # or multi-root by design, and lossless passthrough is orthogonal to
        # single-root validation (#257 owns that).
        assert all(isinstance(segment, str) for segment in parser.segments), (
            "fixtures for this class must be custom-tag-free; "
            "a ChildRef appeared, so something got cut"
        )
        segments: list[str | ChildRef | RenderedLevel] = list(parser.segments)
        level = RenderedLevel(
            segments=segments,
            # serialize never reads root_span (segments.py:448); a rootless
            # fixture parses to None, so substitute a harmless span rather than
            # widening RenderedLevel's type. #262 owns root_span's real value.
            root_span=parser.root_span or (0, 0),
            descriptor=None,
        )
        return serialize(level)

    @pytest.mark.parametrize(
        "markup",
        [
            "<div><p>hi</p></div>",
            '<img src="x.png"/>',
            "<input disabled value=bare data-x='single' data-y=\"double\">",
            "<!-- note -->",
            "<!DOCTYPE html>",
            "<div><p>hi</div>",
            "</span>hi",
            "<3 and 2 < 4",
            "plain text, no markup at all",
            "",
        ],
    )
    def test_round_trips_core_markup(self, markup: str):
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        [
            "<DIV>hi</DIV>",
            "<div>\n<p>a</p>\n</DIV>",
            "</DIV >",
            "<p>x</p >",
            "<div\n  id='a'\n  class='b'\n>x</div>",
        ],
    )
    def test_round_trips_casing_and_intra_tag_whitespace(self, markup: str):
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        [
            "a &amp; b &#65; c",
            "&nbsp;&lt;div&gt;",
            "<p>&unknown;</p>",
            "text with & bare ampersand",
            "<a href=/x?q=1&y=2>link</a>",
            "<p title='a&amp;b'>t</p>",
        ],
    )
    def test_round_trips_entities_undecoded_through_the_join(self, markup: str):
        # convert_charrefs=False at the parser plus a verbatim join means no
        # decode/re-encode boundary exists anywhere in the pipeline.
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        [
            '<script>if (a < b && c) { x("q"); }</script>',
            '<style>a[href="x"] > b { content: "&"; }</style>',
            "<script>var s = '</p>';</script>",
            "<SCRIPT>A < B</SCRIPT>",
            "<![CDATA[x]]>",
            "<![if IE]>a<![endif]>",
            "<!--[if IE]>x<![endif]-->",
            "<?php echo 1 ?>",
        ],
    )
    def test_round_trips_cdata_marked_sections_and_pis(self, markup: str):
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        [
            '<div class="card">\n  <h2>Hi</h2>\n  <p>a &amp; b</p>\n</div>',
            "  <div>  <span> x </span>  </div>  ",
            "<ul><li>a<li>b</ul>",
            "<div><!-- c --><br><hr/>t</div>",
            "<my-el data-x>hi</my-el>",
            "\n\n\t  \n",
        ],
    )
    def test_round_trips_multi_segment_compositions(self, markup: str):
        # Whitespace-heavy, deeply segmented and implicitly-closed markup: the
        # cases where a lossy join would show up as collapsed or reordered text.
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        ["<div", "<!-- unclosed"],
    )
    def test_markup_truncated_at_eof_is_a_documented_non_round_trip(self, markup: str):
        # Pinned counter-example, not a gap: HTMLParser.close() drops or
        # completes a construct cut off mid-source, so these cannot round-trip
        # (VerbatimParser docstring, segments.py:166-169). Jinja never emits
        # such output. Asserting the inequality here keeps the class's positive
        # claim honest and makes the day this behaviour changes visible.
        assert self.round_trip(markup) != markup
