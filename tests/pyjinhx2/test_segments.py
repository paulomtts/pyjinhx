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
            '<PJXButton label="Go">text</PJXButton>',
            "<div>\n<p>a</p>\n</DIV>",
            "</DIV >",
            "<p>x</p >",
            "<PJXButton\n  label='Go'\n>t</PJXButton>",
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
        start, end = parser.root_span
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
        start, end = parser.root_span
        assert (start, end) == (0, len('<PJXButton label="Go">'))
        assert markup[start:end] == '<PJXButton label="Go">'

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
        assert "<PJXIcon name='a'/>" in segments
        assert ChildRef(tag="PJXIcon", attrs={"name": "b"}, inner=None) in segments

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
        assert "<PJXIcon name='a'/>" in segments
        assert ChildRef(tag="PJXIcon", attrs={"name": "b"}, inner=None) in segments

    def test_mismatched_close_tag_does_not_pop_or_raise(self):
        # No enforcement until #257: a stray close tag is passed through and the
        # stack is left alone, so the icon is still inside the accordion's span.
        segments = self.parse("<PJXAccordion></PJXOther><PJXIcon name='a'/>")
        assert "</PJXOther>" in segments
        assert "<PJXIcon name='a'/>" in segments

    def test_paired_custom_tags_stay_raw_passthrough(self):
        # Open decision (b) for #254: paired tags are NOT collapsed here. #256 owns
        # the collapse; #254 only records where it starts.
        assert self.parse('<PJXButton label="Go">text</PJXButton>') == [
            '<PJXButton label="Go">',
            "text",
            "</PJXButton>",
        ]
