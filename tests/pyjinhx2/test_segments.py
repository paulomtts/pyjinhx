import ast
import dataclasses
import inspect

import pytest

import pyjinhx2.segments
from pyjinhx2.segments import (
    RE_PASCAL_CASE_TAG_NAME,
    ChildRef,
    RenderedLevel,
    VerbatimParser,
    contains_custom_tag,
    serialize,
    splice,
)


def make_level(
    segments: "list[str | ChildRef | RenderedLevel] | None" = None,
    root_span: tuple[int, int] = (0, 5),
    descriptor: object = None,
) -> "RenderedLevel":
    if segments is None:
        segments = ["<div>hi</div>"]
    return RenderedLevel(segments=segments, root_span=root_span, descriptor=descriptor)


def make_child_ref(
    tag: str = "PJXButton",
    attrs: "dict[str, str] | None" = None,
    inner: "str | None" = None,
) -> "ChildRef":
    if attrs is None:
        attrs = {"label": "Go"}
    return ChildRef(tag=tag, attrs=attrs, inner=inner)


class TestRenderedLevel:
    def test_holds_its_three_fields(self):
        level = make_level()
        assert level.segments == ["<div>hi</div>"]
        assert level.root_span == (0, 5)
        assert level.descriptor is None

    def test_segments_mutate_in_place(self):
        child = make_level(segments=["<button>go</button>"])
        parent = make_level(segments=["<div>", "PLACEHOLDER", "</div>"])
        parent.segments[1] = child
        assert parent.segments[1] is child

    def test_nested_levels_are_whole_objects(self):
        child = make_level()
        parent = make_level(segments=["<div>", child, "</div>"])
        assert parent.segments[1] is child

    def test_child_ref_holds_position_in_segments(self):
        child = make_level()
        ref = make_child_ref()
        parent = make_level(segments=["<div>", ref, child, "</div>"])
        assert parent.segments == ["<div>", ref, child, "</div>"]
        assert parent.segments[1] is ref
        assert parent.segments[2] is child

    def test_equality_by_value(self):
        assert make_level() == make_level()
        assert make_level() != make_level(root_span=(1, 6))

    def test_slots_reject_undeclared_attributes(self):
        level = make_level()
        with pytest.raises(AttributeError):
            level.markup = "nope"  # pyright: ignore[reportAttributeAccessIssue]

    def test_is_a_slotted_dataclass(self):
        fields = {f.name for f in dataclasses.fields(RenderedLevel)}
        assert fields == {"segments", "root_span", "descriptor"}
        assert not hasattr(make_level(), "__dict__")


class TestChildRef:
    def test_holds_its_three_fields(self):
        ref = make_child_ref(
            tag="PJXAccordion",
            attrs={"title": "Details"},
            inner="<p>body</p>",
        )
        assert ref.tag == "PJXAccordion"
        assert ref.attrs == {"title": "Details"}
        assert ref.inner == "<p>body</p>"

    def test_inner_is_none_for_self_closing_tags(self):
        ref = make_child_ref(tag="PJXIcon", attrs={"name": "gear"}, inner=None)
        assert ref.inner is None

    def test_equality_by_value(self):
        assert make_child_ref() == make_child_ref()
        assert make_child_ref() != make_child_ref(tag="PJXIcon")
        assert make_child_ref() != make_child_ref(attrs={"label": "Stop"})
        assert make_child_ref() != make_child_ref(inner="<p>body</p>")

    def test_slots_reject_undeclared_attributes(self):
        ref = make_child_ref()
        with pytest.raises(AttributeError):
            ref.resolved = "nope"  # pyright: ignore[reportAttributeAccessIssue]

    def test_is_a_slotted_dataclass(self):
        fields = {f.name for f in dataclasses.fields(ChildRef)}
        assert fields == {"tag", "attrs", "inner"}
        assert not hasattr(make_child_ref(), "__dict__")


def test_segments_module_is_import_pure():
    tree = ast.parse(inspect.getsource(pyjinhx2.segments))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "segments.py must not use relative imports"
            names = [node.module or ""]
        else:
            continue
        internal = [n for n in names if n.startswith("pyjinhx")]
        assert not internal, f"segments.py must not import internal modules: {internal}"


class TestContainsCustomTag:
    @pytest.mark.parametrize(
        ("markup", "expected"),
        [
            ("", False),
            ("just some plain text, no angle brackets", False),
            ("<div>hi</div>", False),
            ("<my-el>hi</my-el>", False),
            ("<ABC>hi</ABC>", False),
            ("<3 and 2 < 4", False),
            ('<PJXButton label="Go">', True),
            ('<div><PJXIcon name="gear"/></div>', True),
            ('<PJXIcon name="gear"/>', True),
            ("< PJXButton>", True),
            ("<div>text</div><PJXButton>Go</PJXButton>", True),
        ],
    )
    def test_detects_pascal_case_tags(self, markup: str, expected: bool):
        assert contains_custom_tag(markup) is expected

    def test_pascal_case_regex_matches_bare_tag_names(self):
        assert RE_PASCAL_CASE_TAG_NAME.match("PJXButton")
        assert RE_PASCAL_CASE_TAG_NAME.match("Button2")
        assert not RE_PASCAL_CASE_TAG_NAME.match("PJX")
        assert not RE_PASCAL_CASE_TAG_NAME.match("div")
        assert not RE_PASCAL_CASE_TAG_NAME.match("My-El")

    def test_does_not_instantiate_a_parser(self):
        source = inspect.getsource(contains_custom_tag)
        assert "HTMLParser" not in source
        assert "html.parser" not in source


class TestVerbatimParser:
    @staticmethod
    def round_trip(markup: str) -> str:
        parser = VerbatimParser()
        parser.feed(markup)
        parser.close()
        # #254 makes `segments` heterogeneous: a top-level self-closing custom tag
        # is cut into a ChildRef, which has no lossless text form here (attribute
        # quoting and order are not preserved on the dataclass). Markup that cuts
        # is asserted structurally instead — see the ChildRef tests below.
        assert all(isinstance(segment, str) for segment in parser.segments), (
            "round_trip only handles all-string segment lists; "
            "assert cut markup structurally instead"
        )
        # str() is a no-op on the str elements the assert above just verified;
        # it exists so basedpyright sees a `str` return type without the assert
        # narrowing `list[str | ChildRef]` (which it does not do through `all()`).
        return "".join(str(segment) for segment in parser.segments)

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
    def test_round_trips_verbatim(self, markup: str):
        assert self.round_trip(markup) == markup

    def test_segments_is_a_flat_list_of_strings(self):
        parser = VerbatimParser()
        parser.feed("<div>hi</div>")
        parser.close()
        assert parser.segments == ["<div>", "hi", "</div>"]

    @pytest.mark.parametrize(
        "markup",
        [
            "<DIV>hi</DIV>",
            "<div>\n<p>a</p>\n</DIV>",
            "</DIV >",
            "<p>x</p >",
        ],
    )
    def test_round_trips_end_tag_casing_and_spacing(self, markup: str):
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
    def test_round_trips_entities_without_decoding(self, markup: str):
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        [
            '<script>if (a < b && c) { x("q"); }</script>',
            '<style>a[href="x"] > b { content: "&"; }</style>',
            "<script>var s = '</p>';</script>",
            "<SCRIPT>A < B</SCRIPT>",
        ],
    )
    def test_cdata_bodies_are_never_re_escaped(self, markup: str):
        # Regression guard for the deliberate deviation from pyjinhx/tags.py:127:
        # v0.x re-escapes handle_data with markupsafe.escape and needs a CDATA
        # exemption to stop `&&` becoming `&amp;&amp;`. v2 escapes nothing, so
        # JS/CSS bodies survive by construction.
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        [
            "<![CDATA[x]]>",
            "<![if IE]>a<![endif]>",
            "<!--[if IE]>x<![endif]-->",
            "<?php echo 1 ?>",
        ],
    )
    def test_round_trips_marked_sections_and_processing_instructions(self, markup: str):
        assert self.round_trip(markup) == markup

    @pytest.mark.parametrize(
        "markup",
        [
            "<PJXAccordion><PJXIcon name='gear'/>",
            "<PJXButton>go",
            "<div><PJXButton>go</div>",
        ],
    )
    def test_unclosed_component_tags_do_not_raise(self, markup: str):
        # Deliberate difference from v0.x pyjinhx/tags.py, whose Parser.close()
        # raises ValueError on an unclosed component stack. #254 added a stack,
        # but purely as cut-gating bookkeeping — enforcement arrives with #257.
        assert self.round_trip(markup) == markup

    @staticmethod
    def parse(markup: str) -> "list[str | ChildRef]":
        parser = VerbatimParser()
        parser.feed(markup)
        parser.close()
        return parser.segments

    @staticmethod
    def parsed(markup: str) -> "VerbatimParser":
        parser = VerbatimParser()
        parser.feed(markup)
        parser.close()
        return parser

    def test_root_span_starts_none_and_stays_none_without_a_root(self):
        assert VerbatimParser().root_span is None
        assert self.parsed("plain text, no markup at all").root_span is None
        assert self.parsed("").root_span is None
        assert self.parsed("&amp; just an entity").root_span is None

    def test_root_span_covers_a_plain_opening_tag(self):
        assert self.parsed("<div><p>hi</p></div>").root_span == (0, len("<div>"))

    def test_root_span_matches_the_architecture_overview_example(self):
        markup = (
            '<div class="card">\n  <h2>Hello</h2>\n  <PJXButton label="Save"/>\n'
            '  <p>hi</p>\n  <PJXIcon name="gear"/>\n</div>'
        )
        parser = self.parsed(markup)
        assert parser.root_span == (0, 18)
        span = parser.root_span
        assert span is not None
        start, end = span
        assert markup[start:end] == '<div class="card">'

    def test_root_span_covers_a_cut_top_level_self_closing_tag(self):
        markup = '<PJXIcon name="gear"/>'
        parser = self.parsed(markup)
        # The cut into a ChildRef (#254) and the span capture (#255) are orthogonal:
        # both come off the same raw tag text.
        assert parser.segments == [
            ChildRef(tag="PJXIcon", attrs={"name": "gear"}, inner=None)
        ]
        assert parser.root_span == (0, len(markup))

    def test_root_span_covers_a_plain_self_closing_tag(self):
        markup = '<img src="x.png"/>'
        assert self.parsed(markup).root_span == (0, len(markup))

    def test_root_span_covers_only_the_opening_tag_of_a_paired_custom_tag(self):
        markup = '<PJXButton label="Go">text</PJXButton>'
        parser = self.parsed(markup)
        span = parser.root_span
        assert span is not None
        start, end = span
        assert (start, end) == (0, len('<PJXButton label="Go">'))
        assert markup[start:end] == '<PJXButton label="Go">'

    def test_root_span_records_only_the_first_of_several_top_level_siblings(self):
        # Multi-root rejection is #257's; #255 just must not get confused by it.
        markup = '<PJXButton label="Go"/> and <PJXIcon name="gear"/>'
        parser = self.parsed(markup)
        span = parser.root_span
        assert span is not None
        start, end = span
        assert markup[start:end] == '<PJXButton label="Go"/>'
        assert (start, end) == (0, 23)

    def test_root_span_records_the_outer_tag_not_a_nested_one(self):
        markup = "<PJXAccordion><PJXIcon name='gear'/></PJXAccordion>"
        parser = self.parsed(markup)
        span = parser.root_span
        assert span is not None
        start, end = span
        assert markup[start:end] == "<PJXAccordion>"
        assert (start, end) == (0, len("<PJXAccordion>"))

    def test_root_span_ignores_tag_name_casing(self):
        # Unlike _custom_tag_name, span capture makes no PascalCase distinction.
        assert self.parsed("<DIV>hi</DIV>").root_span == (0, len("<DIV>"))

    def test_root_span_end_is_start_plus_raw_length_for_irregular_tag_text(self):
        markup = "<PJXButton\n  label='Go'\n>t</PJXButton>"
        parser = self.parsed(markup)
        span = parser.root_span
        assert span is not None
        start, end = span
        raw = "<PJXButton\n  label='Go'\n>"
        assert markup[start:end] == raw
        assert end - start == len(raw)

    def test_root_span_is_absolute_across_leading_newlines(self):
        # Offsets are into the whole fed source, resolved through _line_starts, so a
        # tag on a later line still slices back to its own raw text.
        markup = "\n\n  <div class='card'>hi</div>"
        parser = self.parsed(markup)
        span = parser.root_span
        assert span is not None
        start, end = span
        assert markup[start:end] == "<div class='card'>"

    def test_top_level_self_closing_tag_becomes_a_child_ref(self):
        assert self.parse('<div><PJXIcon name="gear"/></div>') == [
            "<div>",
            ChildRef(tag="PJXIcon", attrs={"name": "gear"}, inner=None),
            "</div>",
        ]

    def test_cut_preserves_original_tag_casing(self):
        # HTMLParser hands handle_startendtag a lowercased `pjxbutton`; the cut
        # must come from the source text instead.
        segments = self.parse('<PJXButton label="Go"/>')
        assert isinstance(segments[0], ChildRef)
        assert segments[0].tag == "PJXButton"

    def test_bare_attrs_become_empty_strings(self):
        segments = self.parse('<PJXButton disabled label="Go"/>')
        assert isinstance(segments[0], ChildRef)
        assert segments[0].attrs == {"disabled": "", "label": "Go"}

    def test_sibling_self_closing_tags_cut_in_document_order(self):
        assert self.parse('<PJXButton label="Go"/> and <PJXIcon name="gear"/>') == [
            ChildRef(tag="PJXButton", attrs={"label": "Go"}, inner=None),
            " and ",
            ChildRef(tag="PJXIcon", attrs={"name": "gear"}, inner=None),
        ]

    def test_plain_self_closing_tags_are_not_cut(self):
        assert self.parse('<img src="x.png"/>') == ['<img src="x.png"/>']

    def test_self_closing_tag_inside_open_custom_tag_is_not_cut(self):
        segments = self.parse("<PJXAccordion><PJXIcon name='gear'/>")
        # Only the ancestor's span matters here; the nested icon stays raw text so
        # #256 can capture it wholesale into PJXAccordion's `inner`.
        assert "<PJXIcon name='gear'/>" in segments
        assert not any(isinstance(segment, ChildRef) for segment in segments)

    def test_cut_resumes_after_the_custom_tag_closes(self):
        segments = self.parse(
            "<PJXAccordion><PJXIcon name='a'/></PJXAccordion><PJXIcon name='b'/>"
        )
        # The nested icon was never cut — it is raw text inside the accordion's
        # body — but the sibling after the close tag is top-level again.
        assert segments == [
            ChildRef(tag="PJXAccordion", attrs={}, inner="<PJXIcon name='a'/>"),
            ChildRef(tag="PJXIcon", attrs={"name": "b"}, inner=None),
        ]

    def test_plain_tags_do_not_disturb_the_custom_tag_stack(self):
        # <div> is not a component, so it neither pushes nor pops: the accordion is
        # still open across it, and the icon inside is still not cut.
        segments = self.parse("<PJXAccordion><div></div><PJXIcon name='a'/>")
        assert "<PJXIcon name='a'/>" in segments
        assert not any(isinstance(segment, ChildRef) for segment in segments)

    def test_nested_custom_tags_pop_at_the_right_level(self):
        segments = self.parse(
            "<PJXAccordion><PJXPanel></PJXPanel><PJXIcon name='a'/></PJXAccordion>"
            "<PJXIcon name='b'/>"
        )
        # </PJXPanel> pops its own entry but does not collapse: the stack is still
        # non-empty, so the panel stays verbatim inside the accordion's body.
        assert segments == [
            ChildRef(
                tag="PJXAccordion",
                attrs={},
                inner="<PJXPanel></PJXPanel><PJXIcon name='a'/>",
            ),
            ChildRef(tag="PJXIcon", attrs={"name": "b"}, inner=None),
        ]

    def test_mismatched_close_tag_does_not_pop_or_raise(self):
        # No enforcement until #257: a stray close tag is passed through and the
        # stack is left alone, so the icon is still inside the accordion's span.
        segments = self.parse("<PJXAccordion></PJXOther><PJXIcon name='a'/>")
        assert "</PJXOther>" in segments
        assert "<PJXIcon name='a'/>" in segments

    def test_paired_custom_tag_collapses_into_one_child_ref(self):
        # #254 left the open tag, body and close tag as three raw strings; #256
        # collapses that run into a single ChildRef carrying the raw body.
        assert self.parse('<PJXButton label="Go">text</PJXButton>') == [
            ChildRef(tag="PJXButton", attrs={"label": "Go"}, inner="text"),
        ]

    def test_paired_custom_tag_with_empty_body_has_empty_inner(self):
        assert self.parse("<PJXButton></PJXButton>") == [
            ChildRef(tag="PJXButton", attrs={}, inner=""),
        ]

    def test_bare_attrs_on_a_paired_open_tag_become_empty_strings(self):
        # Same _attrs_to_dict convention as the self-closing cut.
        segments = self.parse('<PJXButton disabled label="Go">go</PJXButton>')
        assert segments == [
            ChildRef(
                tag="PJXButton", attrs={"disabled": "", "label": "Go"}, inner="go"
            ),
        ]

    def test_collapse_survives_casing_and_whitespace_in_the_open_tag(self):
        # HTMLParser hands handle_starttag a lowercased `pjxbutton`; the name must
        # come from the source text, and the newlines inside the open tag must not
        # leak into `inner`.
        segments = self.parse("<PJXButton\n  label='Go'\n>t</PJXButton>")
        assert segments == [
            ChildRef(tag="PJXButton", attrs={"label": "Go"}, inner="t"),
        ]

    def test_nested_paired_tag_is_captured_wholesale_into_inner(self):
        # ADR 0002: a component's body is opaque here. </PJXPanel> must not
        # produce its own ChildRef, and must not truncate the accordion's run.
        segments = self.parse("<PJXAccordion><PJXPanel>body</PJXPanel></PJXAccordion>")
        assert segments == [
            ChildRef(
                tag="PJXAccordion",
                attrs={},
                inner="<PJXPanel>body</PJXPanel>",
            ),
        ]

    def test_nested_self_closing_tag_stays_raw_inside_inner(self):
        segments = self.parse("<PJXAccordion><PJXIcon name='a'/></PJXAccordion>")
        assert segments == [
            ChildRef(tag="PJXAccordion", attrs={}, inner="<PJXIcon name='a'/>"),
        ]

    def test_sibling_paired_and_self_closing_tags_resolve_independently(self):
        assert self.parse(
            '<PJXButton label="Go">text</PJXButton> and <PJXIcon name="gear"/>'
        ) == [
            ChildRef(tag="PJXButton", attrs={"label": "Go"}, inner="text"),
            " and ",
            ChildRef(tag="PJXIcon", attrs={"name": "gear"}, inner=None),
        ]


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
        source = inspect.getsource(pyjinhx2.segments)
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
