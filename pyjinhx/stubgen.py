"""Generate `.pyi` stubs for the `.pjx` documents that carry a Python block.

A type-checker does not read `.pjx`, so ``card.pjx`` with a ``{#python`` block
gets a ``card.pyi`` beside it. The stub is the block's Python with every
function body replaced by ``...``, and every class, def and field keeps the
line it has in the ``.pjx`` file.

Import-pure — stdlib and `pyjinhx.sfc` only. The block is parsed, never run.
"""

import ast
from collections.abc import Iterator

from pyjinhx.sfc import python_block, python_source

_MARKER_PREFIX = "# pyjinhx.stubgen: generated from "


def marker(pjx_name: str) -> str:
    """The comment that marks a stub as generated from ``pjx_name``."""
    return f"{_MARKER_PREFIX}{pjx_name}; do not edit"


def _functions(
    body: list[ast.stmt],
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The outermost functions under ``body``, found through classes and
    compound statements such as ``if`` and ``try`` but not into a function."""
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node
            continue
        for field in ("body", "orelse", "finalbody"):
            yield from _functions(getattr(node, field, []))
        for handler in getattr(node, "handlers", []):
            yield from _functions(handler.body)
        for case in getattr(node, "cases", []):
            yield from _functions(case.body)


def generate_stub(source: str, filename: str) -> str | None:
    """The stub for the ``.pjx`` document ``source``, or None without a block.

    Raises:
        BlockSyntaxError: The block is malformed.
        SyntaxError: The block's Python does not parse; ``lineno`` is the
            line in the document.
    """
    python = python_source(source, filename)
    block = python_block(source, filename)
    if python is None or block is None:
        return None
    tree = ast.parse(python, filename=filename)
    # ast columns are UTF-8 byte offsets, so edit bytes, not text.
    data = python.encode()
    starts = [0]
    for line in data.split(b"\n")[:-1]:
        starts.append(starts[-1] + len(line) + 1)
    edits = []
    for function in _functions(tree.body):
        first, last = function.body[0], function.body[-1]
        assert last.end_lineno is not None and last.end_col_offset is not None
        begin = starts[first.lineno - 1] + first.col_offset
        end = starts[last.end_lineno - 1] + last.end_col_offset
        edits.append((begin, end, last.end_lineno - first.lineno))
    # Bottom-up, so an edit never moves the offsets of those still to apply.
    for begin, end, newlines in sorted(edits, reverse=True):
        # The newlines keep the lines below the body where they were.
        data = data[:begin] + b"..." + b"\n" * newlines + data[end:]
    lines = data.decode().split("\n")
    lines[block.open_line - 1] = marker(filename.replace("\\", "/").split("/")[-1])
    return "\n".join(lines)
