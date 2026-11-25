"""What an editor needs to know about a project's components, without running it.

``python -m pyjinhx.manifest [paths]`` prints one JSON document describing every
component under the paths; ``--grammar`` prints the block grammar as data.
Everything is read with ``ast`` and the block scanners. No application module is
imported and no block is run, so it is safe on an untrusted or broken tree.
"""

import argparse
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from pyjinhx.sfc import BLOCK_KEYWORDS, BlockSyntaxError, python_block


def _column(line: str, offset: int) -> int:
    """The 0-based UTF-16 column of the 1-based character ``offset`` in ``line``."""
    return len(line[: max(offset - 1, 0)].encode("utf-16-le")) // 2


def _recorded(keyword: str, opened: int, closed: int) -> dict[str, Any]:
    """One block as the manifest lists it. A ``def`` has no ``body_lines``: a header is one expression."""
    block: dict[str, Any] = {"keyword": keyword, "open_line": opened}
    if keyword != "def":
        block["body_lines"] = [opened + 1, closed - 1] if closed - opened > 1 else None
    block["close_line"] = closed
    return block


def scan_blocks(
    source: str, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The blocks of the document ``source`` and the grammar errors in it.

    Blocks come in file order. Each error is a ``code``, 1-based ``line``,
    0-based UTF-16 ``column`` and ``message``; a malformed block is an error
    and not a block, and one error does not hide another.
    """
    # Local: template_blocks imports jinja2, which a bare `import pyjinhx.manifest`
    # does not need.
    from pyjinhx.template_blocks import (
        BlockTemplateSyntaxError,
        find_block,
        inline_assets,
    )

    lines = source.split("\n")
    blocks: list[dict[str, Any]] = []
    errors: dict[tuple[str, int], dict[str, Any]] = {}

    def fail(error: Exception) -> None:
        code = getattr(error, "code", "")
        line = getattr(error, "lineno", None) or 1
        message = getattr(error, "msg", None) or getattr(error, "message", "")
        offset = getattr(error, "offset", None) or 1
        text = lines[line - 1] if line <= len(lines) else ""
        errors.setdefault(
            (code, line),
            {
                "code": code,
                "line": line,
                "column": _column(text, offset),
                "message": message,
            },
        )

    for keyword in BLOCK_KEYWORDS:
        try:
            if keyword == "python":
                python = python_block(source, filename)
                found = python and (python.open_line, python.close_line)
            else:
                block = find_block(source, keyword, filename)
                found = block and (block.line, block.close_line)
        except (BlockSyntaxError, BlockTemplateSyntaxError) as e:
            fail(e)
            continue
        if found:
            blocks.append(_recorded(keyword, *found))
    try:
        inline_assets(Path(filename), source)
    except (BlockSyntaxError, BlockTemplateSyntaxError) as e:
        fail(e)
    blocks.sort(key=lambda block: block["open_line"])
    return blocks, sorted(errors.values(), key=lambda e: (e["line"], e["column"]))


def grammar_text() -> str:
    """The text of ``block_grammar.json``, the block grammar as data."""
    return resources.files("pyjinhx").joinpath("block_grammar.json").read_text("utf-8")


def main(argv: list[str] | None = None) -> int:
    """The command line: ``python -m pyjinhx.manifest [--grammar] [paths]``."""
    parser = argparse.ArgumentParser(
        prog="python -m pyjinhx.manifest",
        description="Describe the components under the paths as JSON, "
        "without importing them.",
    )
    parser.add_argument(
        "--grammar", action="store_true", help="print the block grammar and exit"
    )
    args = parser.parse_args(argv)
    if args.grammar:
        sys.stdout.write(grammar_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
