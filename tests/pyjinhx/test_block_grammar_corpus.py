"""The block grammar corpus: every case under tests/fixtures/block_grammar,
scanned with the real scanners, must give the recorded blocks or error."""

import json
from pathlib import Path

import pytest
from jinja2 import TemplateSyntaxError

from pyjinhx import sfc
from pyjinhx.template_blocks import find_block, inline_assets

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "block_grammar"


def _scan(source: str, filename: str) -> tuple[list[dict], dict | None]:
    """The blocks and first error the scanners report for ``source``."""
    blocks = []
    try:
        for keyword in ("def", "css", "js"):
            try:
                block = find_block(source, keyword, filename)
            except TemplateSyntaxError as error:
                return [], {"code": sfc.SECOND_BLOCK, "line": error.lineno}
            if block is not None:
                blocks.append((keyword, block.line, block.close_line))
        python = sfc.python_block(source, filename)
    except sfc.BlockSyntaxError as error:
        return [], {"code": error.code, "line": error.lineno}
    if python is not None:
        blocks.append(("python", python.open_line, python.close_line))
    try:
        inline_assets(Path(filename), source)
    except TemplateSyntaxError as error:
        return [], {"code": sfc.STRAY_COMMENT_CLOSE, "line": error.lineno}
    except sfc.BlockSyntaxError as error:
        return [], {"code": error.code, "line": error.lineno}
    return [
        {
            "keyword": keyword,
            "open_line": opened,
            "body_lines": [opened + 1, closed - 1] if closed - opened > 1 else None,
            "close_line": closed,
        }
        for keyword, opened, closed in sorted(blocks, key=lambda b: b[1])
    ], None


@pytest.mark.parametrize("case", sorted(CORPUS.glob("*.pjx")), ids=lambda p: p.stem)
def test_the_scanners_agree_with_the_recorded_case(case):
    expected = json.loads(case.with_suffix(".json").read_text(encoding="utf-8"))
    source = case.read_bytes().decode("utf-8")

    blocks, error = _scan(source, case.name)

    assert (blocks, error) == (expected["blocks"], expected["error"])


def test_the_corpus_has_a_case_for_every_error_code():
    codes = {
        json.loads(path.read_text())["error"]["code"]
        for path in CORPUS.glob("*.json")
        if json.loads(path.read_text())["error"]
    }

    assert codes == {
        sfc.PYTHON_BLOCK_EARLY_CLOSE,
        sfc.SECOND_BLOCK,
        sfc.OPENER_NOT_AT_LINE_START,
        sfc.TEXT_AFTER_CLOSER,
        sfc.STRAY_COMMENT_CLOSE,
    }
