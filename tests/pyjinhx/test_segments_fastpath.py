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


def parse(parser: VerbatimParser, chunks: list[str]) -> tuple[list[object], object]:
    for chunk in chunks:
        parser.feed(chunk)
    parser.close()
    return parser.segments, parser.root_span


def assert_identical_parse(chunks: list[str]) -> list[object]:
    """Fast-path and slow-path parses agree on segments, root_span and round-trip."""
    fast_segments, fast_span = parse(VerbatimParser(), chunks)
    slow_segments, slow_span = parse(SlowParser(), chunks)
    assert fast_segments == slow_segments
    assert fast_span == slow_span
    source = "".join(chunks)
    if all(not isinstance(seg, ChildRef) for seg in fast_segments):
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
