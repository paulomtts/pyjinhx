"""Generate `.pyi` stubs for the `.pjx` documents that carry a Python block.

A type-checker does not read `.pjx`, so ``card.pjx`` with a ``{#python`` block
gets a ``card.pyi`` beside it. The stub is the block's Python with every
function body replaced by ``...``, and every class, def and field keeps the
line it has in the ``.pjx`` file.

Import-pure — stdlib and `pyjinhx.sfc` only. The block is parsed, never run.

Limits of a stub worth knowing:

- Annotate return types in blocks: an unannotated ``def`` has no body in the
  stub to infer from, so its return type is ``Unknown``.
- Stricter Pyright modes flag the stub's statements and unused imports. Keep
  the stubs resolvable but unchecked with ``ignore`` (not ``exclude``), e.g.
  ``ignore = ["app/components/**/*.pyi"]`` under ``[tool.pyright]``.
- A stub does not re-export a block's imports: import a name from the module
  that defines it, not from the ``.pjx``'s stub.
- ``__init__`` bodies are kept as written, since their ``self.x = ...``
  statements declare the instance attributes.
"""

import argparse
import ast
import os
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import NamedTuple

from pyjinhx.sfc import normalize_text, python_block

_MARKER_PREFIX = "# pyjinhx.stubgen: generated from "


def marker(pjx_name: str) -> str:
    """The comment that marks a stub as generated from ``pjx_name``."""
    return f"{_MARKER_PREFIX}{pjx_name}; do not edit"


def _functions(
    body: list[ast.stmt],
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The outermost functions under ``body``, bar ``__init__``, found through classes and
    compound statements such as ``if`` and ``try`` but not into a function."""
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # An `__init__` body is what declares the instance attributes.
            if node.name != "__init__":
                yield node
            continue
        for field in ("body", "orelse", "finalbody"):
            yield from _functions(getattr(node, field, []))
        for handler in getattr(node, "handlers", []):
            yield from _functions(handler.body)
        for case in getattr(node, "cases", []):
            yield from _functions(case.body)


def generate_stub(source: str, filename: str) -> str | None:
    """The stub for the ``.pjx`` document ``source``, or None without a block
    (the file is no document unless a line starts with ``{#python``).

    Raises:
        BlockSyntaxError: The block is malformed.
        SyntaxError: The block's Python does not parse; ``lineno`` is the
            line in the document.
    """
    source = normalize_text(source)
    block = python_block(source, filename)
    if block is None:
        return None
    python = block.source
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


MISSING = "missing"
STALE = "stale"
ORPHANED = "orphaned"
SHADOWED = "shadowed"
HANDWRITTEN = "handwritten"
INVALID = "invalid"
FAILED = "failed"

# What each fixable finding becomes once `sync` has written it.
_DONE = {MISSING: "wrote", STALE: "rewrote", ORPHANED: "removed"}

_SKIPPED_DIRS = {
    "__pycache__",
    "node_modules",
    "site-packages",
    "dist-packages",
    "build",
    "dist",
}


class Finding(NamedTuple):
    """One thing `sync` found out of order, or fixed.

    ``path`` is the stub for ``missing``, ``stale``, ``orphaned`` and
    ``handwritten``, and the ``.pjx`` document for ``shadowed`` and
    ``invalid``, which also carry the ``line``, the 1-based ``column`` and the
    ``code`` of a malformed block when known, and a ``message``. ``failed`` is
    a stub that could not be written or removed, at its ``path``.
    """

    path: Path
    kind: str
    line: int | None = None
    message: str = ""
    code: str | None = None
    column: int | None = None


def stub_path(pjx: Path) -> Path:
    """Where the stub of the document ``pjx`` lives: beside it."""
    return pjx.with_suffix(".pyi")


def is_generated(stub: Path) -> bool:
    """Whether ``stub`` carries the generator's marker, so is ours to touch."""
    try:
        text = stub.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(line.startswith(_MARKER_PREFIX) for line in text.splitlines())


def walk(paths: Iterable[Path], suffixes: set[str]) -> dict[str, list[Path]]:
    """The files under ``paths`` with each of ``suffixes``, sorted, by suffix.
    Hidden directories, virtualenvs (any with a ``pyvenv.cfg``), installed
    packages, build output, ``__pycache__`` and ``node_modules`` are skipped."""
    found: dict[str, set[Path]] = {suffix: set() for suffix in suffixes}
    for path in paths:
        if path.is_file():
            if path.suffix in suffixes:
                found[path.suffix].add(path)
            continue
        for directory, names, files in os.walk(path):
            names[:] = [
                n
                for n in names
                if not n.startswith(".")
                and n not in _SKIPPED_DIRS
                and not Path(directory, n, "pyvenv.cfg").exists()
            ]
            for name in files:
                file = Path(directory, name)
                if file.suffix in suffixes:
                    found[file.suffix].add(file)
    return {suffix: sorted(files) for suffix, files in found.items()}


def sync(paths: Iterable[Path], *, write: bool) -> list[Finding]:
    """Bring the stubs under ``paths`` in line with their ``.pjx`` documents.

    A stub that is missing or stale is written, an orphaned one removed, but
    only with ``write``; without it nothing on disk changes. Either way every
    such stub, and every problem that needs a person, is returned: a hand-
    written stub in a stub's place, a ``.py`` module or package that shadows a
    block, a block that does not parse. Files without the generator's marker
    are never overwritten or removed.
    """
    found = walk((Path(p) for p in paths), {".pjx", ".pyi"})
    documents, stubs = found[".pjx"], found[".pyi"]
    findings: list[Finding] = []
    live: set[Path] = set()
    for document in documents:
        try:
            source = document.read_text(encoding="utf-8")
            stub = generate_stub(source, str(document))
        except SyntaxError as error:
            findings.append(
                Finding(
                    document,
                    INVALID,
                    error.lineno,
                    error.msg or str(error),
                    getattr(error, "code", None),
                    error.offset,
                )
            )
            live.add(stub_path(document))
            continue
        except (UnicodeDecodeError, OSError) as error:
            findings.append(Finding(document, INVALID, None, str(error)))
            live.add(stub_path(document))
            continue
        if stub is None:
            continue
        target = stub_path(document)
        live.add(target)
        if document.with_suffix(".py").exists() or document.with_suffix("").is_dir():
            findings.append(Finding(document, SHADOWED))
            continue
        if not target.exists():
            findings.append(Finding(target, MISSING))
        elif not is_generated(target):
            findings.append(Finding(target, HANDWRITTEN))
            continue
        elif target.read_bytes() == stub.encode():
            continue
        else:
            findings.append(Finding(target, STALE))
        if write:
            try:
                target.write_bytes(stub.encode())
            except OSError as error:
                findings[-1] = Finding(target, FAILED, message=str(error))
    for stub in stubs:
        if stub not in live and is_generated(stub):
            findings.append(Finding(stub, ORPHANED))
            if write:
                try:
                    stub.unlink()
                except OSError as error:
                    findings[-1] = Finding(stub, FAILED, message=str(error))
    return sorted(findings)


def _show(finding: Finding, done: bool) -> str:
    where = str(_relative(finding.path))
    if finding.line:
        where += f":{finding.line}"
        if finding.column:
            where += f":{finding.column}"
    what = _DONE[finding.kind] if done and finding.kind in _DONE else finding.kind
    detail = " ".join(filter(None, [finding.code, finding.message]))
    return f"{where}: {what}" + (f" ({detail})" if detail else "")


def _relative(path: Path) -> Path:
    try:
        return path.relative_to(Path.cwd())
    except ValueError:
        return path


def main(argv: list[str] | None = None) -> int:
    """The command line: ``python -m pyjinhx.stubgen [--check] [path ...]``.

    Exits 0 when every stub is as it should be, 1 when a stub was stale,
    missing or orphaned under ``--check`` or something needs a person, and 2
    when a hand-written ``.pyi`` is in a stub's way or a path does not exist.
    """
    parser = argparse.ArgumentParser(
        prog="python -m pyjinhx.stubgen",
        description="Write a .pyi beside every .pjx document with a {#python block.",
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[Path()], help="files or directories"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; exit 1 listing stale, missing and orphaned stubs",
    )
    args = parser.parse_args(argv)
    missing = [p for p in args.paths if not p.exists()]
    for path in missing:
        print(f"{path}: no such file or directory", file=sys.stderr)
    if missing:
        return 2
    findings = sync(args.paths, write=not args.check)
    for finding in findings:
        fixed = not args.check and finding.kind in _DONE
        print(_show(finding, fixed), file=sys.stdout if fixed else sys.stderr)
    unresolved = [f for f in findings if args.check or f.kind not in _DONE]
    if any(f.kind == HANDWRITTEN for f in unresolved):
        return 2
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
