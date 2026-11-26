"""The block grammar corpus: every case under tests/fixtures/block_grammar,
scanned with the real scanners, must give the recorded blocks or error."""

import json
from pathlib import Path

import pytest

from pyjinhx import manifest
from pyjinhx.document import scanner
from pyjinhx.document.template_blocks import (
    BlockTemplateSyntaxError,
    find_block,
    inline_assets,
)

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "block_grammar"


def _scan(source: str, filename: str) -> tuple[list[dict], dict | None]:
    """The blocks and the lowest-line error the scanners report for ``source``."""
    blocks: list[tuple[str, int, int]] = []
    errors: list[BlockTemplateSyntaxError | scanner.BlockSyntaxError] = []
    for keyword in ("def", "css", "js"):
        try:
            block = find_block(source, keyword, filename)
        except BlockTemplateSyntaxError as error:
            errors.append(error)
        else:
            if block is not None:
                blocks.append((keyword, block.line, block.close_line))
    try:
        python = scanner.python_block(source, filename)
    except scanner.BlockSyntaxError as error:
        errors.append(error)
    else:
        if python is not None:
            blocks.append(("python", python.open_line, python.close_line))
    try:
        inline_assets(Path(filename), source)
    except (BlockTemplateSyntaxError, scanner.BlockSyntaxError) as error:
        errors.append(error)
    if errors:
        first = min(errors, key=lambda error: error.lineno or 0)
        return [], {"code": first.code, "line": first.lineno}
    return [_recorded(*block) for block in sorted(blocks, key=lambda b: b[1])], None


def _recorded(keyword: str, opened: int, closed: int) -> dict:
    """A block as the corpus writes it down."""
    block: dict = {"keyword": keyword, "open_line": opened}
    if keyword != "def":
        block["body_lines"] = [opened + 1, closed - 1] if closed - opened > 1 else None
    block["close_line"] = closed
    return block


@pytest.mark.parametrize("case", sorted(CORPUS.glob("*.pjx")), ids=lambda p: p.stem)
def test_the_scanners_agree_with_the_recorded_case(case, request):
    expected = json.loads(case.with_suffix(".json").read_text(encoding="utf-8"))
    source = case.read_bytes().decode("utf-8-sig")

    if "known_gap" in expected:
        # Jinja's own answer is recorded; pyjinhx differs, and this fails
        # loudly once it stops.
        request.applymarker(pytest.mark.xfail(strict=True, reason="known_gap"))

    blocks, error = _scan(source, case.name)

    assert (blocks, error) == (expected["blocks"], expected["error"])


def test_the_corpus_has_a_case_for_every_error_code():
    recorded = (
        json.loads(path.read_text(encoding="utf-8")) for path in CORPUS.glob("*.json")
    )

    assert {case["error"]["code"] for case in recorded if case["error"]} == {
        scanner.PYTHON_BLOCK_EARLY_CLOSE,
        scanner.SECOND_BLOCK,
        scanner.CLOSER_NOT_AT_LINE_START,
        scanner.UNCLOSED_BLOCK,
        scanner.TEXT_AFTER_CLOSER,
        scanner.STRAY_COMMENT_CLOSE,
    }


@pytest.mark.parametrize("case", sorted(CORPUS.glob("*.pjx")), ids=lambda p: p.stem)
def test_the_manifest_scan_agrees_with_the_recorded_case(case, request):
    expected = json.loads(case.with_suffix(".json").read_text(encoding="utf-8"))
    source = case.read_bytes().decode("utf-8-sig")

    if "known_gap" in expected:
        request.applymarker(pytest.mark.xfail(strict=True, reason="known_gap"))

    blocks, errors = manifest.scan_blocks(source, case.name)

    if expected["error"]:
        assert (errors[0]["code"], errors[0]["range"]["start"]["line"]) == (
            expected["error"]["code"],
            expected["error"]["line"],
        )
    else:
        assert errors == []
        assert blocks == expected["blocks"]
