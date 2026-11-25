"""What an editor needs to know about a project's components, without running it.

``python -m pyjinhx.manifest [paths]`` prints one JSON document describing every
component under the paths; ``--grammar`` prints the block grammar as data.
Everything is read with ``ast`` and the block scanners. No application module is
imported and no block is run, so it is safe on an untrusted or broken tree.
"""

import argparse
import ast
import json
import os
import re
import sys
from collections.abc import Callable
from importlib import resources
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, NamedTuple

from pyjinhx.sfc import (
    BLOCK_KEYWORDS,
    BlockSyntaxError,
    _is_one_literal,
    _template_value,
    comments,
    extract_template,
    python_block,
)
from pyjinhx.stubgen import HANDWRITTEN, MISSING, ORPHANED, STALE, stub_path, sync, walk

MANIFEST_VERSION = 1


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


# `_component._pascal_to_snake`, copied: importing it would pull in pydantic.
# A test keeps the two the same.
_PASCAL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# `discovery._SNAKE_CASE_RE` and `props_header._HEADER_RE`, copied for the same
# reason: the stems a component can have, and the legacy spaced header, which
# only counts as the first thing in the document.
_SNAKE_RE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
_LEGACY_HEADER_RE = re.compile(
    r"\A\s*(?:\{#\s*#\}\s*)?\{#\s*def\s+(?P<sig>.*?)\s*#\}", re.DOTALL
)
_HEADER_PREFIX = "def __pjx_props__("
_DEFINITION_RE = re.compile(r"(?:async\s+)?(?:class|def)\s+")


def _snake(name: str) -> str:
    return _PASCAL_BOUNDARY_RE.sub("_", name).lower()


def _pascal(stem: str) -> str:
    return "".join(word.capitalize() for word in stem.split("_"))


def module_name_for(path: Path) -> str:
    """The dotted module name of the file ``path``: its stem under every
    parent directory that holds an ``__init__.py``, as pytest names it.

    Pure over the filesystem, so it works on a file that does not exist yet.
    """
    path = Path(os.path.normpath(Path(path).absolute()))
    parts = [] if path.stem == "__init__" else [path.stem]
    directory = path.parent
    while (directory / "__init__.py").exists():
        parts.append(directory.name)
        directory = directory.parent
    return ".".join(reversed(parts))


def _display(path: Path) -> str:
    """``path`` as a POSIX string, relative to the working directory if under it."""
    path = Path(os.path.normpath(Path(path).absolute()))
    try:
        path = path.relative_to(Path.cwd())
    except ValueError:
        pass
    return path.as_posix()


def _col(lines: list[str], lineno: int, byte_offset: int) -> int:
    """The 0-based UTF-16 column of ``ast``'s UTF-8 ``byte_offset`` on a line."""
    before = lines[lineno - 1].encode()[:byte_offset].decode("utf-8", "ignore")
    return len(before.encode("utf-16-le")) // 2


def _name_column(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]
) -> int:
    """The UTF-16 column of the name in a ``class`` or ``def`` statement."""
    line = lines[node.lineno - 1]
    start = len(line.encode()[: node.col_offset].decode("utf-8", "ignore"))
    keyword = _DEFINITION_RE.match(line, start)
    end = start + (len(keyword.group()) if keyword else 0)
    return len(line[:end].encode("utf-16-le")) // 2


def _tail(node: ast.expr) -> str | None:
    """The last name of ``node``: ``a.b.C``, ``C[...]`` and ``C()`` give ``C``."""
    match node:
        case ast.Name(id=name) | ast.Attribute(attr=name):
            return name
        case ast.Subscript(value=value) | ast.Call(func=value):
            return _tail(value)
    return None


def _names_in(node: ast.expr) -> set[str]:
    names = (_tail(n) for n in ast.walk(node) if isinstance(n, ast.expr))
    return {name for name in names if name}


def _literal_values(annotation: ast.expr | None) -> list[Any] | None:
    """The members of a ``Literal[...]`` annotation, or None. ``X | None`` and
    ``Optional[X]`` are looked through."""
    match annotation:
        case ast.Subscript(slice=members) if _tail(annotation) == "Literal":
            elements = members.elts if isinstance(members, ast.Tuple) else [members]
            try:
                values = [ast.literal_eval(element) for element in elements]
            except ValueError:
                return None
            plain = all(v is None or isinstance(v, str | int | float) for v in values)
            return values if plain else None
        case ast.Subscript(slice=inner) if _tail(annotation) == "Optional":
            return _literal_values(inner)
        case ast.BinOp(op=ast.BitOr(), left=left, right=right):
            return _literal_values(left) or _literal_values(right)
    return None


def _prop(
    name: str,
    annotation: ast.expr | None,
    default: ast.expr | None,
    text: str,
    position: tuple[int, int],
) -> dict[str, Any]:
    """One prop: annotation and default as written, plus what they mean."""
    if default is None or (
        isinstance(default, ast.Constant) and default.value is Ellipsis
    ):
        required, written = True, None
    else:
        required, written = False, ast.get_source_segment(text, default)
    names = _names_in(annotation) if annotation is not None else set()
    return {
        "name": name,
        "annotation": ast.get_source_segment(text, annotation) if annotation else None,
        "required": required,
        "default": written,
        "literal_values": _literal_values(annotation),
        "slot": "Slot" in names,
        "children": "Children" in names,
        "line": position[0],
        "column": position[1],
    }


def _class_props(node: ast.ClassDef, text: str, lines: list[str]) -> list[dict]:
    """The annotated fields of a class body. Private names and ``ClassVar``
    are not fields."""
    props = []
    for field in node.body:
        if not (
            isinstance(field, ast.AnnAssign)
            and isinstance(field.target, ast.Name)
            and not field.target.id.startswith("_")
            and "ClassVar" not in _names_in(field.annotation)
        ):
            continue
        target = field.target
        position = (target.lineno, _col(lines, target.lineno, target.col_offset))
        props.append(_prop(target.id, field.annotation, field.value, text, position))
    return props


def _members(node: ast.ClassDef, lines: list[str]) -> list[dict[str, Any]]:
    """The properties, methods and classmethods of a class body that a
    template can reach: public names, a property's setter left out."""
    members = []
    for member in node.body:
        if not isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        decorators = {_tail(d) for d in member.decorator_list}
        if member.name.startswith("_") or decorators & {"setter", "deleter"}:
            continue
        if "classmethod" in decorators:
            kind = "classmethod"
        elif decorators & {"property", "cached_property"}:
            kind = "property"
        else:
            kind = "method"
        members.append(
            {
                "name": member.name,
                "kind": kind,
                "line": member.lineno,
                "column": _name_column(member, lines),
            }
        )
    return members


def _class_info(
    node: ast.ClassDef, text: str, lines: list[str], path: Path
) -> dict[str, Any]:
    return {
        "module": module_name_for(path),
        "qualname": node.name,
        "path": _display(path),
        "line": node.lineno,
        "column": _name_column(node, lines),
        "bases": [ast.get_source_segment(text, base) for base in node.bases],
        "stub": None,
    }


def _markup_lines(source: str) -> list[int] | None:
    """The first and last line holding anything but comments and whitespace."""
    text = source
    for comment in reversed(list(comments(source))):
        blank = "\n" * comment.group().count("\n")
        text = text[: comment.start()] + blank + text[comment.end() :]
    numbered = [n for n, line in enumerate(text.split("\n"), 1) if line.strip()]
    return [numbered[0], numbered[-1]] if numbered else None


def _header(source: str) -> tuple[str, int] | None:
    """The ``{#def#}`` signature text and where it starts in ``source``."""
    from pyjinhx.template_blocks import BlockTemplateSyntaxError, find_block

    try:
        block = find_block(source, "def", "")
    except BlockTemplateSyntaxError:
        return None
    if block is not None:
        line_start = len(source) - len(source.split("\n", block.line - 1)[-1])
        return block.body, source.index(block.body, line_start)
    legacy = _LEGACY_HEADER_RE.match(source)
    return (legacy.group("sig"), legacy.start("sig")) if legacy else None


def _header_props(source: str, lines: list[str]) -> list[dict] | SyntaxError:
    """The props a ``{#def#}`` header declares, read as a signature and never
    resolved: a dotted name in it is text here, not an import."""
    found = _header(source)
    if found is None:
        return []
    signature, offset = found
    code = f"{_HEADER_PREFIX}{signature}): pass"
    try:
        function = ast.parse(code).body[0]
    except SyntaxError as error:
        return error
    assert isinstance(function, ast.FunctionDef)
    first = source.count("\n", 0, offset) + 1
    first_byte = len(source[source.rfind("\n", 0, offset) + 1 : offset].encode())
    args = function.args.args
    missing = [None] * (len(args) - len(function.args.defaults))
    props = []
    for arg, default in zip(args, missing + function.args.defaults, strict=True):
        if arg.lineno == 1:
            line, byte = first, first_byte + arg.col_offset - len(_HEADER_PREFIX)
        else:
            line, byte = first + arg.lineno - 1, arg.col_offset
        position = (line, _col(lines, line, byte))
        props.append(_prop(arg.arg, arg.annotation, default, code, position))
    return props


def _template_span(text: str, lines: list[str], node: ast.expr) -> dict[str, Any]:
    """Where the contents of the string literal ``node`` start and end,
    between its quotes."""
    assert node.end_lineno is not None and node.end_col_offset is not None
    literal = ast.get_source_segment(text, node) or ""
    prefix = len(literal) - len(literal.lstrip("rRuU"))
    quote = 3 if literal[prefix : prefix + 3] in ('"""', "'''") else 1
    start = _col(lines, node.lineno, node.col_offset) + prefix + quote
    end = _col(lines, node.end_lineno, node.end_col_offset) - quote
    return {
        "start": {"line": node.lineno, "column": start},
        "end": {"line": node.end_lineno, "column": end},
    }


def _component(
    tag: str,
    kind: str,
    document: dict[str, Any],
    blocks: list[dict[str, Any]],
    class_info: dict[str, Any] | None = None,
    props: list[dict[str, Any]] | None = None,
    members: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "tag": tag,
        "kind": kind,
        "document": document,
        "blocks": blocks,
        "class": class_info,
        "props": props or [],
        "members": members or [],
    }


def _report(
    diagnostics: list[dict[str, Any]],
    path: Path,
    line: int,
    column: int,
    code: str,
    message: str,
    severity: str = "error",
) -> None:
    diagnostics.append(
        {
            "path": _display(path),
            "line": line,
            "column": column,
            "severity": severity,
            "code": code,
            "message": message,
        }
    )


class _Document(NamedTuple):
    """A ``.pjx`` file as read: its text and the blocks found in it."""

    path: Path
    source: str
    blocks: list[dict[str, Any]]


def _has_python(document: _Document) -> bool:
    return any(block["keyword"] == "python" for block in document.blocks)


def _inline_component(
    node: ast.ClassDef,
    value: ast.expr,
    path: Path,
    text: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    """The component for a class that assigns ``template`` in a ``.py`` module."""
    lines = text.split("\n")
    assert value.end_lineno is not None
    document: dict[str, Any] = {
        "path": _display(path),
        "markup_lines": [value.lineno, value.end_lineno],
    }
    blocks: list[dict[str, Any]] = []
    literal = (
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and _is_one_literal(text, value)
    )
    if not literal:
        _report(
            diagnostics,
            path,
            value.lineno,
            _col(lines, value.lineno, value.col_offset),
            "template-not-literal",
            f"{node.name}.template must be one plain string literal: it is read "
            "from the source text, so an f-string, a concatenation or a name "
            "cannot be used",
        )
    else:
        document["span"] = _template_span(text, lines, value)
        try:
            template = extract_template(text, node.name, str(path))
        except ValueError:
            pass
        else:
            # The template's lines are the module's, but its columns are those
            # of the dedented text, so a column inside it is approximate.
            blocks, errors = scan_blocks(template, str(path))
            for error in errors:
                _report(
                    diagnostics,
                    path,
                    error["line"],
                    error["column"],
                    error["code"],
                    error["message"],
                )
    return _component(
        node.name,
        "py-template",
        document,
        blocks,
        _class_info(node, text, lines, path),
        _class_props(node, text, lines),
        _members(node, lines),
    )


def _py_components(
    path: Path,
    read: Callable[[Path], str],
    documents: dict[Path, _Document],
    claimed: set[Path],
    pjx_dirs: set[Path],
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The components a ``.py`` module declares: a class that assigns
    ``template``, or one with a ``<snake_name>.pjx`` beside the module."""
    try:
        text = read(path)
    except (OSError, UnicodeDecodeError):
        return []
    # Most modules are neither: skip the parse unless the text or a neighbour
    # could make a class a component.
    if "template" not in text and path.parent not in pjx_dirs:
        return []
    try:
        tree = ast.parse(text, str(path))
    except (SyntaxError, ValueError):
        return []
    lines = text.split("\n")
    found = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        value = _template_value(node)
        if value is not None:
            found.append(_inline_component(node, value, path, text, diagnostics))
            continue
        sibling = path.with_name(f"{_snake(node.name)}.pjx")
        document = documents.get(sibling)
        if document is None or _has_python(document):
            continue
        claimed.add(sibling)
        found.append(
            _component(
                node.name,
                "split",
                {
                    "path": _display(sibling),
                    "markup_lines": _markup_lines(document.source),
                },
                document.blocks,
                _class_info(node, text, lines, path),
                _class_props(node, text, lines),
                _members(node, lines),
            )
        )
    return found


def _python_component(
    document: _Document, py_paths: set[Path], diagnostics: list[dict[str, Any]]
) -> dict[str, Any]:
    """The component a ``.pjx`` document with a ``{#python`` block declares,
    and every reason pyjinhx would refuse it."""
    path, source, blocks = document
    block = python_block(source, str(path))
    assert block is not None
    text = "\n" * block.open_line + block.body
    lines = text.split("\n")
    source_lines = source.split("\n")

    def refuse(code: str, message: str, line: int = block.open_line, column: int = 0):
        _report(diagnostics, path, line, column, code, message)

    for found in blocks:
        if found["keyword"] == "def":
            line = found["open_line"]
            column = _column(
                source_lines[line - 1], source_lines[line - 1].find("{#") + 1
            )
            refuse(
                "def-with-python",
                "a {#def#} header and a {#python block in one document: the "
                "class declares the props, so remove the header",
                line,
                column,
            )
    markup = _markup_lines(source)
    if markup is None:
        refuse("no-markup", "a document with a {#python block needs some markup")
    if (
        path.with_suffix(".py") in py_paths
        or path.with_suffix(".py").exists()
        or path.with_suffix("").is_dir()
    ):
        refuse(
            "shadowed-by-module",
            f"{path.stem}.py or {path.stem}/ sits beside this document, so Python "
            "imports that and never reaches the block",
        )
    class_info = props = members = None
    tag = _pascal(path.stem)
    try:
        tree = ast.parse(text, str(path))
    except SyntaxError as error:
        line = error.lineno or block.open_line
        refuse(
            "python-syntax-error",
            error.msg,
            line,
            _column(lines[line - 1], error.offset or 1),
        )
    else:
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        for node in classes:
            value = _template_value(node)
            if value is not None:
                refuse(
                    "template-in-block",
                    f"{node.name} assigns template, but the document is its template",
                    value.lineno,
                    _col(lines, value.lineno, value.col_offset),
                )
        named = [n for n in classes if _snake(n.name) == path.stem]
        if not named:
            refuse(
                "no-component-class",
                f"the block defines no class named for the file: expected one "
                f"whose snake_case name is {path.stem!r}",
            )
        else:
            if len(named) > 1:
                refuse(
                    "ambiguous-component-class",
                    f"{named[0].name} and {named[1].name} both snake to {path.stem!r}",
                    named[1].lineno,
                    _name_column(named[1], lines),
                )
            tag = named[0].name
            class_info = _class_info(named[0], text, lines, path)
            if stub_path(path).exists():
                class_info["stub"] = _display(stub_path(path))
            props = _class_props(named[0], text, lines)
            members = _members(named[0], lines)
    return _component(
        tag,
        "pjx-python",
        {"path": _display(path), "markup_lines": markup},
        blocks,
        class_info,
        props,
        members,
    )


def _template_component(
    document: _Document, diagnostics: list[dict[str, Any]]
) -> dict[str, Any]:
    """The component of a ``.pjx`` document no class claims: props from its
    ``{#def#}`` header, if it has one."""
    path, source, blocks = document
    props = _header_props(source, source.split("\n"))
    if isinstance(props, SyntaxError):
        _report(
            diagnostics,
            path,
            1,
            0,
            "def-header-invalid",
            f"the {{#def#}} header is not a valid signature: {props.msg}",
        )
        props = []
    return _component(
        _pascal(path.stem),
        "template",
        {"path": _display(path), "markup_lines": _markup_lines(source)},
        blocks,
        props=props,
    )


def _build(
    pjx_paths: list[Path], py_paths: list[Path], read: Callable[[Path], str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every component and diagnostic in the given ``.pjx`` and ``.py`` files."""
    diagnostics: list[dict[str, Any]] = []
    documents: dict[Path, _Document] = {}
    for path in pjx_paths:
        try:
            source = read(path)
        except (OSError, UnicodeDecodeError) as error:
            _report(diagnostics, path, 1, 0, "unreadable-file", str(error))
            continue
        blocks, errors = scan_blocks(source, str(path))
        for error in errors:
            _report(
                diagnostics,
                path,
                error["line"],
                error["column"],
                error["code"],
                error["message"],
            )
        documents[path] = _Document(path, source, blocks)
    components: list[dict[str, Any]] = []
    claimed: set[Path] = set()
    pjx_dirs = {path.parent for path in documents}
    for path in py_paths:
        components += _py_components(
            path, read, documents, claimed, pjx_dirs, diagnostics
        )
    for document in documents.values():
        if document.path in claimed:
            continue
        if _has_python(document):
            components.append(_python_component(document, set(py_paths), diagnostics))
        elif "{#python" not in document.source and _SNAKE_RE.fullmatch(
            document.path.stem
        ):
            components.append(_template_component(document, diagnostics))
    return components, diagnostics


def _read(path: Path) -> str:
    """The text of ``path`` with a byte order mark and ``\\r`` line breaks gone."""
    text = path.read_text(encoding="utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _stub_diagnostics(
    paths: list[Path], components: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Stubs that are missing, stale, orphaned or hand-written, from stubgen."""
    opened = {
        c["document"]["path"]: next(
            b["open_line"] for b in c["blocks"] if b["keyword"] == "python"
        )
        for c in components
        if c["kind"] == "pjx-python"
        and any(b["keyword"] == "python" for b in c["blocks"])
    }
    advice = {
        MISSING: "no stub beside this document; run python -m pyjinhx.stubgen",
        STALE: "the stub is out of date; run python -m pyjinhx.stubgen",
        HANDWRITTEN: "a hand-written .pyi is in the stub's place and is never "
        "overwritten",
        ORPHANED: "a generated stub whose document is gone or has no python block",
    }
    diagnostics: list[dict[str, Any]] = []
    for finding in sync(paths, write=False):
        if finding.kind not in advice:
            continue
        orphaned = finding.kind == ORPHANED
        path = finding.path if orphaned else finding.path.with_suffix(".pjx")
        line = 1 if orphaned else opened.get(_display(path), 1)
        _report(
            diagnostics,
            path,
            line,
            0,
            f"stub-{finding.kind}",
            advice[finding.kind],
            "warning",
        )
    return diagnostics


def _manifest(
    roots: list[Path], components: list[dict[str, Any]], diagnostics: list[dict]
) -> dict[str, Any]:
    components.sort(
        key=lambda c: (
            c["document"]["path"],
            c["class"]["line"] if c["class"] else 0,
            c["tag"],
        )
    )
    diagnostics.sort(key=lambda d: (d["path"], d["line"], d["column"], d["code"]))
    try:
        installed = version("pyjinhx")
    except PackageNotFoundError:
        installed = "unknown"
    return {
        "manifest_version": MANIFEST_VERSION,
        "grammar_version": json.loads(grammar_text())["version"],
        "pyjinhx_version": installed,
        "roots": [_display(root) for root in roots],
        "components": components,
        "diagnostics": diagnostics,
    }


def describe(paths: list[Path]) -> dict[str, Any]:
    """The manifest of every component under ``paths``, as a JSON-ready dict."""
    paths = [Path(p) for p in paths]
    found = walk(paths, {".pjx", ".py"})
    components, diagnostics = _build(found[".pjx"], found[".py"], _read)
    diagnostics += _stub_diagnostics(paths, components)
    return _manifest(paths, components, diagnostics)


def describe_buffer(filename: Path, text: str) -> dict[str, Any]:
    """The manifest entries and diagnostics of one file, as the editor holds it.

    ``text`` stands in for the file on disk, which may not exist or may be
    older. Its neighbours in the same directory are read from disk, because
    whether it is a component depends on them. No stub diagnostics: the
    buffer's stub is a file on disk, and it is the editor's to regenerate.
    """
    file = Path(filename)
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    names = {file, *file.parent.glob("*.pjx"), *file.parent.glob("*.py")}
    pjx = sorted(p for p in names if p.suffix == ".pjx")
    py = sorted(p for p in names if p.suffix == ".py")
    components, diagnostics = _build(
        pjx, py, lambda path: text if path == file else _read(path)
    )
    shown = _display(file)
    components = [
        c
        for c in components
        if shown in (c["document"]["path"], (c["class"] or {}).get("path"))
    ]
    diagnostics = [d for d in diagnostics if d["path"] == shown]
    return _manifest([file], components, diagnostics)


def grammar_text() -> str:
    """The text of ``block_grammar.json``, the block grammar as data."""
    return resources.files("pyjinhx").joinpath("block_grammar.json").read_text("utf-8")


def main(argv: list[str] | None = None) -> int:
    """The command line:
    ``python -m pyjinhx.manifest [--grammar] [--stdin --filename F] [paths]``.

    Prints JSON and exits 0, diagnostics included: they are data. Exits 2 for
    a path that does not exist or a bad combination of options.
    """
    parser = argparse.ArgumentParser(
        prog="python -m pyjinhx.manifest",
        description="Describe the components under the paths as JSON, "
        "without importing them.",
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[Path()], help="files or directories"
    )
    parser.add_argument(
        "--grammar", action="store_true", help="print the block grammar and exit"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="describe the text on standard input as the file --filename",
    )
    parser.add_argument("--filename", type=Path, help="where the --stdin text lives")
    args = parser.parse_args(argv)
    if args.grammar:
        sys.stdout.write(grammar_text())
        return 0
    if args.stdin:
        if args.filename is None:
            parser.error("--stdin needs --filename")
        text = sys.stdin.buffer.read().decode("utf-8", "replace")
        result = describe_buffer(args.filename, text)
    else:
        missing = [p for p in args.paths if not p.exists()]
        for path in missing:
            print(f"{path}: no such file or directory", file=sys.stderr)
        if missing:
            return 2
        result = describe(args.paths)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
