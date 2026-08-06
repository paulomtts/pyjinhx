"""Fast-path parity checks for VerbatimParser.

Lightweight sanity coverage taken while prototyping the tag-free fast path;
the systematic split-tag / entity-ref / literal-`<` suite lives elsewhere.
"""

from html.parser import HTMLParser

import pytest

from pyjinhx.segments import ChildRef, VerbatimParser


class SlowParser(VerbatimParser):
    """VerbatimParser with the fast path disabled: every chunk goes to HTMLParser."""

    def feed(self, data: str) -> None:
        self._source = data
        self._line_starts = [0] + [i + 1 for i, char in enumerate(data) if char == "\n"]
        HTMLParser.feed(self, data)


def parse(
    parser: VerbatimParser, chunks: list[str]
) -> tuple[list[str | ChildRef], tuple[int, int] | None]:
    for chunk in chunks:
        parser.feed(chunk)
    parser.close()
    return parser.segments, parser.root_span


def assert_identical_parse(
    chunks: list[str], *, round_trip: bool = True
) -> list[str | ChildRef]:
    """Fast-path and slow-path parses agree on segments, root_span and round-trip.

    ``round_trip=False`` covers inputs HTMLParser deliberately normalizes (close
    tags lowercased, ``&nbsp`` completed to ``&nbsp;``) or drops (a construct cut
    off at a feed boundary), where reconstruction can never equal the source.
    """
    fast_segments, fast_span = parse(VerbatimParser(), chunks)
    slow_segments, slow_span = parse(SlowParser(), chunks)
    assert fast_segments == slow_segments
    assert fast_span == slow_span
    source = "".join(chunks)
    if round_trip and all(not isinstance(seg, ChildRef) for seg in fast_segments):
        assert "".join(str(seg) for seg in fast_segments) == source
    return fast_segments


@pytest.mark.parametrize(
    "chunks",
    [
        ["plain text with no markup at all"],
        ["a" * 5000],
        ["line one\nline two\nline three\n"],
        ["tag free chunk ", "<div>then markup</div>", " and tag free tail"],
        ["", "still nothing", ""],
        ["  \n\t  "],
        ["<PJXButton>body</PJXButton>", " tail", " more tag free text"],
    ],
)
def test_fast_path_matches_slow_path(chunks: list[str]) -> None:
    assert_identical_parse(chunks)


def test_tag_free_chunk_is_one_data_segment() -> None:
    segments = assert_identical_parse(["no markup here"])
    assert segments == ["no markup here"]


@pytest.mark.parametrize(
    ("label", "chunks"),
    [
        ("before the opener", ["prefix ", '<PJXButton kind="a"/> suffix']),
        ("right after the opener", ["prefix <", 'PJXButton kind="a"/> suffix']),
        ("inside the tag name", ["prefix <PJXBut", 'ton kind="a"/> suffix']),
        ("inside an attribute name", ["prefix <PJXButton ki", 'nd="a"/> suffix']),
        ("inside a quoted value", ['prefix <PJXButton kind="a', '"/> suffix']),
        ("inside an unquoted value", ["prefix <PJXButton kind=a", " /> suffix"]),
        ("between attributes", ['prefix <PJXButton kind="a" ', 'size="b"/> suffix']),
        ("at the self-closing slash", ['prefix <PJXButton kind="a"/', "> suffix"]),
    ],
)
def test_split_position_variants_for_component_tag(
    label: str, chunks: list[str]
) -> None:
    """A self-closing component tag still collapses to one ChildRef wherever the split lands."""
    segments = assert_identical_parse(chunks)
    refs = [seg for seg in segments if isinstance(seg, ChildRef)]
    assert len(refs) == 1, label
    assert refs[0].tag == "PJXButton"
    assert refs[0].inner is None
    assert refs[0].attrs["kind"] == "a"


def test_multi_chunk_split_across_more_than_two_feeds() -> None:
    """One tag spread over five feed() calls still yields a single ChildRef."""
    segments = assert_identical_parse(["<PJX", "But", "ton ", 'kind="a"', "/>"])
    assert segments == [ChildRef(tag="PJXButton", attrs={"kind": "a"}, inner=None)]


def test_open_close_component_split_body_does_not_collapse() -> None:
    """A split inside the body of an open/close component leaves raw segments: collapsing
    an open/close pair into one ChildRef only happens when the whole tag is seen in a
    single feed(); this records that both parsers agree on the (non-collapsed) result."""
    segments = assert_identical_parse(
        ["<PJXCard>bo", "dy</PJXCard>"], round_trip=False
    )
    assert segments == ["<PJXCard>", "bo", "dy", "</pjxcard>"]


@pytest.mark.parametrize(
    "chunks",
    [
        ["<PJXButton>body</PJX", "Button> tail"],
        ["<PJXButton>body</", "PJXButton> tail"],
        ["<PJXButton>body</PJXButton", "> tail"],
    ],
)
def test_split_inside_closing_tag(chunks: list[str]) -> None:
    """A split inside the closing tag leaves raw segments — the close tag is lowercased,
    so the open tag never collapses into a ChildRef."""
    segments = assert_identical_parse(chunks, round_trip=False)
    assert segments == ["<PJXButton>", "body", "</pjxbutton>", " tail"]


def test_entity_and_char_refs_stay_separate_segments() -> None:
    segments = assert_identical_parse(["a &amp; b &#38; c"])
    assert segments == ["a ", "&amp;", " b ", "&#38;", " c"]


def test_literal_less_than_that_is_not_a_tag() -> None:
    assert_identical_parse(["3 < 5 and 5 > 3"])
    assert_identical_parse(["cost < ", "10 dollars"])


def test_known_lossy_case_can_skip_round_trip() -> None:
    """A construct truncated at a feed boundary parses identically but does not round-trip."""
    segments = assert_identical_parse(["end with <", "more"], round_trip=False)
    assert segments == ["end with "]
