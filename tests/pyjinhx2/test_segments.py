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
        return "".join(parser.segments)

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
            '<PJXIcon name="gear"/>',
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
