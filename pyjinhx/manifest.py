"""What an editor needs to know about a project's components, without running it.

``python -m pyjinhx.manifest [--sys-path DIR ...] [paths]`` prints one JSON
document describing every component under the paths, and pyjinhx's own
builtins. ``--stdin --filename F`` describes one unsaved buffer instead, and
``--grammar`` prints the block grammar as data. Everything is read with ``ast``
and the block scanners: no application module is imported and no block is run,
so it is safe on an untrusted or broken tree.

Conventions of the JSON:

- Paths are absolute and POSIX, so the output does not depend on where it ran.
- A position is ``{"line", "column"}``: lines are 1-based, columns 0-based
  UTF-16 code units, which is what LSP uses. A range is ``{"start", "end"}`` of
  two positions. The ``range`` of a prop, class, member or diagnostic is that
  of its name or of what is wrong.
- ``annotation`` and ``default`` are source text as written.
- ``class.module`` is the module name Python would import the file under, as
  `sfc.module_name_for` derives it, or null when there is none. With no
  ``--sys-path`` it is the path below the top of the package chain (the
  highest directory holding an ``__init__.py``); with some, a file outside
  that chain is named by the path below the deepest entry that contains it.

Versioning: ``manifest_version`` and ``grammar_version`` change when a field is
removed or renamed, or its meaning changes. A field may be added without a
bump, so a reader ignores keys it does not know.

What static reading cannot see, and so is not in the output:

- A class is a component only if it assigns ``template`` or a
  ``<snake_name>.pjx`` sits beside its module. A subclass that inherits its
  template is not listed, and inherited fields are not in ``props``.
- Whether a class subclasses ``BaseComponent``: a base is a name, and what it
  names needs an import.
- Classes nested in a function or another class.
- ``--stdin`` reads the buffer's neighbours (the files in its directory) from
  disk, so an unsaved neighbour is not seen, and tag collisions are only
  checked among those and the builtins.
"""

import argparse
import ast
import json
import os
import re
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, NamedTuple

from pyjinhx.sfc import (
    BLOCK_KEYWORDS,
    HEADER_PREFIX,
    LEGACY_HEADER_RE,
    LITERAL_ERRORS,
    BlockSyntaxError,
    HeaderSignatureError,
    comments,
    extract_template,
    header_arguments,
    is_component_stem,
    is_one_literal,
    module_name_for,
    opener_line,
    pascal_to_snake,
    python_block,
    source_segment,
    template_value,
)
from pyjinhx.stubgen import HANDWRITTEN, MISSING, ORPHANED, STALE, sync, walk

MANIFEST_VERSION = 1

_DEFINITION_RE = re.compile(r"(?:async\s+)?(?:class|def)\s+")


def _utf16(text: str) -> int:
    """The length of ``text`` in UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def _column(line: str, offset: int) -> int:
    """The 0-based UTF-16 column of the 1-based character ``offset`` in ``line``."""
    return _utf16(line[: max(offset - 1, 0)])


def _col(lines: list[str], lineno: int, byte_offset: int) -> int:
    """The 0-based UTF-16 column of ``ast``'s UTF-8 ``byte_offset`` on a line."""
    before = lines[lineno - 1].encode()[:byte_offset].decode("utf-8", "ignore")
    return _utf16(before)


def _range(line: int, column: int, end_line: int, end_column: int) -> dict[str, Any]:
    return {
        "start": {"line": line, "column": column},
        "end": {"line": end_line, "column": end_column},
    }


def _line_range(lines: list[str], line: int, column: int = 0) -> dict[str, Any]:
    """The range from ``column`` to the end of ``line``."""
    text = lines[line - 1] if 0 < line <= len(lines) else ""
    return _range(line, column, line, max(_utf16(text), column))


def _recorded(keyword: str, opened: int, closed: int) -> dict[str, Any]:
    """One block as the manifest lists it. A ``def`` has no ``body_lines``: a
    header is one expression."""
    block: dict[str, Any] = {"keyword": keyword, "open_line": opened}
    if keyword != "def":
        block["body_lines"] = [opened + 1, closed - 1] if closed - opened > 1 else None
    block["close_line"] = closed
    return block


def scan_blocks(
    source: str, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The blocks of the document ``source`` and the grammar errors in it.

    Blocks come in file order. Each error is a ``code``, a ``range`` and a
    ``message``; a malformed block is an error and not a block, and one error
    does not hide another.
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
        where = _line_range(lines, line, _column(text, offset))
        errors.setdefault(
            (code, line), {"code": code, "range": where, "message": message}
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
    ordered = sorted(errors.values(), key=lambda e: _start(e["range"]))
    return blocks, ordered


def _start(where: dict[str, Any]) -> tuple[int, int]:
    return where["start"]["line"], where["start"]["column"]


def _pascal(stem: str) -> str:
    return "".join(word.capitalize() for word in stem.split("_"))


def _absolute(path: Path | str) -> Path:
    return Path(os.path.normpath(Path(path).absolute()))


def _name_column(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]
) -> int:
    """The UTF-16 column of the name in a ``class`` or ``def`` statement."""
    line = lines[node.lineno - 1]
    start = len(line.encode()[: node.col_offset].decode("utf-8", "ignore"))
    keyword = _DEFINITION_RE.match(line, start)
    end = start + (len(keyword.group()) if keyword else 0)
    return _utf16(line[:end])


def _name_range(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]
) -> dict[str, Any]:
    column = _name_column(node, lines)
    return _range(node.lineno, column, node.lineno, column + _utf16(node.name))


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
            except LITERAL_ERRORS:
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
    where: dict[str, Any],
) -> dict[str, Any]:
    """One prop: annotation and default as written, plus what they mean."""
    if default is None or (
        isinstance(default, ast.Constant) and default.value is Ellipsis
    ):
        required, written = True, None
    else:
        required, written = False, source_segment(text, default)
    names = _names_in(annotation) if annotation is not None else set()
    return {
        "name": name,
        "annotation": source_segment(text, annotation) if annotation else None,
        "required": required,
        "default": written,
        "literal_values": _literal_values(annotation),
        "slot": "Slot" in names,
        "children": "Children" in names,
        "range": where,
    }


def _class_props(node: ast.ClassDef, text: str, lines: list[str]) -> list[dict]:
    """The annotated fields of a class body. Private names and ``ClassVar``
    are not fields."""
    props = []
    for field_ in node.body:
        if not (
            isinstance(field_, ast.AnnAssign)
            and isinstance(field_.target, ast.Name)
            and not field_.target.id.startswith("_")
            and "ClassVar" not in _names_in(field_.annotation)
        ):
            continue
        target = field_.target
        column = _col(lines, target.lineno, target.col_offset)
        where = _range(target.lineno, column, target.lineno, column + _utf16(target.id))
        props.append(_prop(target.id, field_.annotation, field_.value, text, where))
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
                "range": _name_range(member, lines),
            }
        )
    return members


def _replaces(node: ast.ClassDef) -> bool:
    """Whether the class says ``pjx_replace=True``."""
    return any(
        keyword.arg == "pjx_replace"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in node.keywords
    )


def _strict(node: ast.ClassDef) -> bool | None:
    """Whether the class body says ``extra="forbid"`` in its ``model_config``:
    True or False when it names ``extra``, None when it does not (the class
    inherits its setting, which static reading cannot follow)."""
    for statement in node.body:
        match statement:
            case (
                ast.Assign(targets=[ast.Name(id="model_config")], value=config)
                | ast.AnnAssign(target=ast.Name(id="model_config"), value=config)
            ) if config is not None:
                pairs = []
                if isinstance(config, ast.Call):
                    pairs = [(kw.arg, kw.value) for kw in config.keywords]
                elif isinstance(config, ast.Dict):
                    keys = [
                        k.value if isinstance(k, ast.Constant) else None
                        for k in config.keys
                    ]
                    pairs = list(zip(keys, config.values, strict=True))
                for key, value in pairs:
                    if key == "extra" and isinstance(value, ast.Constant):
                        return value.value == "forbid"
    return None


def _class_info(
    node: ast.ClassDef,
    text: str,
    lines: list[str],
    path: Path,
    module: str | None,
) -> dict[str, Any]:
    return {
        "module": module,
        "qualname": node.name,
        "path": path.as_posix(),
        "range": _name_range(node, lines),
        "bases": [source_segment(text, base) for base in node.bases],
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


class _Header(NamedTuple):
    """A ``{#def#}`` header: its signature text, where that starts in the
    document, and the offsets of the ``{#`` and the end of the ``#}``."""

    signature: str
    offset: int
    start: int
    end: int


def _header(source: str) -> _Header | None:
    """The ``{#def#}`` header of ``source``, in either spelling."""
    from pyjinhx.template_blocks import BlockTemplateSyntaxError, find_block

    try:
        block = find_block(source, "def", "")
    except BlockTemplateSyntaxError:
        return None
    if block is not None:
        line_start = len(source) - len(source.split("\n", block.line - 1)[-1])
        offset = source.index(block.body, line_start)
        signature = block.body
    else:
        legacy = LEGACY_HEADER_RE.match(source)
        if legacy is None:
            return None
        offset, signature = legacy.start("sig"), legacy.group("sig")
    end = source.find("#}", offset + len(signature)) + 2
    return _Header(signature, offset, source.rfind("{#", 0, offset), end)


def _where(source: str, offset: int) -> tuple[int, int]:
    """The line and UTF-16 column of ``offset`` in ``source``."""
    line_start = source.rfind("\n", 0, offset) + 1
    return source.count("\n", 0, offset) + 1, _utf16(source[line_start:offset])


def _source_range(source: str, start: int, end: int) -> dict[str, Any]:
    """The range of ``source[start:end]``; an empty one is widened to the end
    of its line, or by one character at the end of the line."""
    if end <= start:
        line_end = source.find("\n", start)
        line_end = len(source) if line_end == -1 else line_end
        end = line_end if line_end > start else start + 1
    return _range(*_where(source, start), *_where(source, end))


def _header_props(
    source: str, header: _Header
) -> tuple[list[dict], tuple[str, dict[str, Any]] | None]:
    """The props a ``{#def#}`` header declares, read as a signature and never
    resolved: a dotted name in it is text here, not an import.

    Also the message and range of what is wrong with the signature, if
    anything is, in which case no props are returned.
    """
    code = f"{HEADER_PREFIX}{header.signature}): pass"
    code_lines = code.split("\n")

    def at(line: int, column: int) -> int:
        """The offset in ``source`` of a character column of ``code``."""
        before = sum(len(text) + 1 for text in code_lines[: line - 1])
        return header.offset + max(before + column - len(HEADER_PREFIX), 0)

    def byte_at(line: int, byte_offset: int) -> int:
        text = code_lines[line - 1].encode()[:byte_offset].decode("utf-8", "ignore")
        return at(line, len(text))

    try:
        pairs = header_arguments(header.signature)
    except HeaderSignatureError as error:
        if error.syntax is not None:
            syntax = error.syntax
            start = at(syntax.lineno or 1, max((syntax.offset or 1) - 1, 0))
            end = at(syntax.end_lineno or syntax.lineno or 1, syntax.end_offset or 0)
        else:
            node: Any = error.node
            start = byte_at(node.lineno, node.col_offset)
            end = byte_at(node.end_lineno or node.lineno, node.end_col_offset or 0)
        limit = header.offset + len(header.signature)
        start = min(start, limit)
        return [], (
            str(error),
            _source_range(source, start, min(max(start, end), limit)),
        )
    props = []
    for arg, default in pairs:
        start = byte_at(arg.lineno, arg.col_offset)
        where = _source_range(source, start, start + len(arg.arg))
        props.append(_prop(arg.arg, arg.annotation, default, code, where))
    return props, None


def _template_span(text: str, lines: list[str], node: ast.expr) -> dict[str, Any]:
    """Where the contents of the string literal ``node`` start and end,
    between its quotes."""
    assert node.end_lineno is not None and node.end_col_offset is not None
    literal = source_segment(text, node)
    prefix = len(literal) - len(literal.lstrip("rRuU"))
    quote = 3 if literal[prefix : prefix + 3] in ('"""', "'''") else 1
    start = _col(lines, node.lineno, node.col_offset) + prefix + quote
    end = _col(lines, node.end_lineno, node.end_col_offset) - quote
    return _range(node.lineno, start, node.end_lineno, end)


def _removed_indent(literal: str) -> int:
    """How many columns of common indentation ``textwrap.dedent`` takes off."""
    kept = textwrap.dedent(literal).split("\n")
    for original, line in zip(literal.split("\n"), kept, strict=True):
        if line.strip():
            return len(original) - len(line)
    return 0


def _assets(directory: Path, stem: str) -> dict[str, str | None]:
    """The sibling stylesheet and script a component named ``stem`` has."""
    return {
        kind: (directory / f"{stem}.{kind}").as_posix()
        if (directory / f"{stem}.{kind}").is_file()
        else None
        for kind in ("css", "js")
    }


def _component(
    tag: str,
    kind: str,
    document: dict[str, Any],
    blocks: list[dict[str, Any]],
    assets: dict[str, str | None],
    class_info: dict[str, Any] | None = None,
    props: list[dict[str, Any]] | None = None,
    members: list[dict[str, Any]] | None = None,
    node: ast.ClassDef | None = None,
    has_stale_def_header: bool = False,
    name: str | None = None,
) -> dict[str, Any]:
    if class_info is None:
        identity = document["path"]
    else:
        identity = f"{class_info['path']}#{class_info['qualname']}"
    return {
        "tag": tag,
        "name": name or pascal_to_snake(tag),
        "id": identity,
        "kind": kind,
        "builtin": False,
        "document": document,
        "blocks": blocks,
        "class": class_info,
        "props": props or [],
        "members": members or [],
        "assets": assets,
        "replaces": node is not None and _replaces(node),
        # A header builds an open model, which accepts extra keys.
        "strict": _strict(node) if node else (False if kind == "template" else None),
        "has_stale_def_header": has_stale_def_header,
    }


class _Document(NamedTuple):
    """A ``.pjx`` file as read: its text and the blocks found in it."""

    path: Path
    source: str
    blocks: list[dict[str, Any]]


def _has_python(document: _Document) -> bool:
    return any(block["keyword"] == "python" for block in document.blocks)


def _diagnostic(
    path: Path, where: dict[str, Any], code: str, message: str, severity: str
) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "range": where,
        "severity": severity,
        "code": code,
        "message": message,
    }


@dataclass
class _Project:
    """What one run reads and finds: the way to read a file, the ``sys.path``
    to name modules by, the documents seen, and the diagnostics so far."""

    read: Callable[[Path], str]
    sys_path: tuple[Path, ...]
    documents: dict[Path, _Document] = field(default_factory=dict)
    py_paths: set[Path] = field(default_factory=set)
    claimed: set[Path] = field(default_factory=set)
    pjx_dirs: set[Path] = field(default_factory=set)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def report(
        self,
        path: Path,
        where: dict[str, Any],
        code: str,
        message: str,
        severity: str = "error",
    ) -> None:
        self.diagnostics.append(_diagnostic(path, where, code, message, severity))

    def module(self, path: Path) -> str | None:
        return module_name_for(path, [str(entry) for entry in self.sys_path])


def _inline_component(
    project: _Project,
    node: ast.ClassDef,
    value: ast.expr,
    path: Path,
    text: str,
) -> dict[str, Any]:
    """The component for a class that assigns ``template`` in a ``.py`` module."""
    lines = text.split("\n")
    assert value.end_lineno is not None
    document: dict[str, Any] = {
        "path": path.as_posix(),
        "markup_lines": [value.lineno, value.end_lineno],
    }
    blocks: list[dict[str, Any]] = []
    literal = (
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and is_one_literal(text, value)
    )
    if not literal:
        column = _col(lines, value.lineno, value.col_offset)
        project.report(
            path,
            _range(value.lineno, column, value.end_lineno, _end_column(lines, value)),
            "template-not-literal",
            f"{node.name}.template must be one plain string literal: it is read "
            "from the source text, so an f-string, a concatenation or a name "
            "cannot be used",
        )
    else:
        assert isinstance(value, ast.Constant)
        document["span"] = _template_span(text, lines, value)
        try:
            template = extract_template(text, node.name, str(path))
        except ValueError:
            pass
        else:
            blocks, errors = scan_blocks(template, str(path))
            indent = _removed_indent(str(value.value))
            first = document["span"]["start"]
            for error in errors:
                # The template is dedented, so its columns lack the indent
                # that the module's lines have; the first line has the quotes.
                for end in error["range"].values():
                    end["column"] += (
                        first["column"] if end["line"] == first["line"] else indent
                    )
                project.report(path, error["range"], error["code"], error["message"])
    stem = pascal_to_snake(node.name)
    return _component(
        node.name,
        "py-template",
        document,
        blocks,
        _assets(path.parent, stem),
        _class_info(node, text, lines, path, project.module(path)),
        _class_props(node, text, lines),
        _members(node, lines),
        node,
    )


def _end_column(lines: list[str], node: ast.expr) -> int:
    assert node.end_lineno is not None and node.end_col_offset is not None
    return _col(lines, node.end_lineno, node.end_col_offset)


def _py_components(project: _Project, path: Path) -> list[dict[str, Any]]:
    """The components a ``.py`` module declares: a class that assigns
    ``template``, or one with a ``<snake_name>.pjx`` beside the module."""
    try:
        text = project.read(path)
    except (OSError, UnicodeDecodeError):
        return []
    # Most modules are neither: skip the parse unless the text or a neighbour
    # could make a class a component.
    if "template" not in text and path.parent not in project.pjx_dirs:
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
        value = template_value(node)
        if value is not None:
            found.append(_inline_component(project, node, value, path, text))
            continue
        sibling = path.with_name(f"{pascal_to_snake(node.name)}.pjx")
        document = project.documents.get(sibling)
        if document is None:
            continue
        if _has_python(document):
            project.report(
                path,
                _name_range(node, lines),
                "class-outside-document",
                f"{sibling.name} holds a {{#python block, so it belongs to the "
                f"class defined there; {node.name} cannot also own it",
            )
            continue
        project.claimed.add(sibling)
        found.append(
            _component(
                node.name,
                "split",
                {
                    "path": sibling.as_posix(),
                    "markup_lines": _markup_lines(document.source),
                },
                document.blocks,
                _assets(sibling.parent, sibling.stem),
                _class_info(node, text, lines, path, project.module(path)),
                _class_props(node, text, lines),
                _members(node, lines),
                node,
                has_stale_def_header=_header(document.source) is not None,
            )
        )
    return found


def _python_components(project: _Project, document: _Document) -> list[dict[str, Any]]:
    """The components a ``.pjx`` document with a ``{#python`` block declares,
    and every reason pyjinhx would refuse it: the class named for the file, then
    any class in the block that subclasses it and so shares its markup."""
    path, source, blocks = document
    block = python_block(source, str(path))
    assert block is not None
    if project.module(path) is None:
        project.report(
            path,
            _line_range(source.split("\n"), block.open_line),
            "no-module-name",
            f"{path.name} cannot be imported: no sys.path entry holds it under "
            "directories that are valid module names",
        )
    text = "\n" * block.open_line + block.body
    lines = text.split("\n")
    source_lines = source.split("\n")
    opener = _line_range(source_lines, block.open_line)

    def refuse(code: str, message: str, where: dict[str, Any] = opener) -> None:
        project.report(path, where, code, message)

    header = _header(source)
    if header is not None:
        refuse(
            "def-with-python",
            "a {#def#} header and a {#python block in one document: the "
            "class declares the props, so remove the header",
            _source_range(source, header.start, header.end),
        )
    markup = _markup_lines(source)
    if markup is None:
        refuse("no-markup", "a document with a {#python block needs some markup")
    if (
        path.with_suffix(".py") in project.py_paths
        or path.with_suffix(".py").exists()
        or path.with_suffix("").is_dir()
    ):
        refuse(
            "shadowed-by-module",
            f"{path.stem}.py or {path.stem}/ sits beside this document, so Python "
            "imports that and never reaches the block",
        )
    class_info = props = members = chosen = None
    inheriting: list[ast.ClassDef] = []
    tag = _pascal(path.stem)
    try:
        tree = ast.parse(text, str(path))
    except SyntaxError as error:
        line = error.lineno or block.open_line
        column = _column(lines[line - 1], error.offset or 1)
        end_line = error.end_lineno or line
        end_column = _column(lines[end_line - 1], error.end_offset or 1)
        if (end_line, end_column) <= (line, column):
            # Nothing to underline: take the rest of the line, or one character.
            end_line, end_column = line, max(_utf16(lines[line - 1]), column + 1)
        refuse(
            "python-syntax-error",
            error.msg,
            _range(line, column, end_line, end_column),
        )
    else:
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        for node in classes:
            value = template_value(node)
            if value is not None:
                column = _col(lines, value.lineno, value.col_offset)
                refuse(
                    "template-in-block",
                    f"{node.name} assigns template, but the document is its template",
                    _range(
                        value.lineno,
                        column,
                        value.end_lineno or value.lineno,
                        _end_column(lines, value),
                    ),
                )
        named = [n for n in classes if pascal_to_snake(n.name) == path.stem]
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
                    _name_range(named[1], lines),
                )
            chosen = named[0]
            tag = chosen.name
            class_info = _class_info(chosen, text, lines, path, project.module(path))
            stub = path.with_suffix(".pyi")
            if stub.exists():
                class_info["stub"] = stub.as_posix()
            props = _class_props(chosen, text, lines)
            members = _members(chosen, lines)
            listed = {chosen.name}
            for node in classes:
                if any(_tail(base) in listed for base in node.bases):
                    listed.add(node.name)
                    inheriting.append(node)
    assets = _assets(path.parent, path.stem)
    document_info = {"path": path.as_posix(), "markup_lines": markup}
    found = [
        _component(
            node.name,
            "pjx-python",
            document_info,
            blocks,
            assets,
            _class_info(node, text, lines, path, project.module(path)),
            _class_props(node, text, lines),
            _members(node, lines),
            node,
        )
        for node in inheriting
    ]
    return [
        _component(
            tag,
            "pjx-python",
            document_info,
            blocks,
            assets,
            class_info,
            props,
            members,
            chosen,
        ),
        *found,
    ]


def _unreadable_python_component(document: _Document) -> dict[str, Any]:
    """The component of a document that opens a ``{#python`` block but has none
    that scans: named for the file, with no class, so it does not vanish from
    the editor while its grammar error is fixed."""
    path, source, blocks = document
    return _component(
        _pascal(path.stem),
        "pjx-python",
        {"path": path.as_posix(), "markup_lines": _markup_lines(source)},
        blocks,
        _assets(path.parent, path.stem),
        name=path.stem,
    )


def _template_component(project: _Project, document: _Document) -> dict[str, Any]:
    """The component of a ``.pjx`` document no class claims: props from its
    ``{#def#}`` header, if it has one."""
    path, source, blocks = document
    props: list[dict] = []
    header = _header(source)
    if header is not None:
        props, problem = _header_props(source, header)
        if problem is not None:
            project.report(
                path,
                problem[1],
                "def-header-invalid",
                f"the {{#def#}} header is not a valid signature: {problem[0]}",
            )
    return _component(
        _pascal(path.stem),
        "template",
        {"path": path.as_posix(), "markup_lines": _markup_lines(source)},
        blocks,
        _assets(path.parent, path.stem),
        props=props,
        name=path.stem,
    )


def _build(
    pjx_paths: list[Path],
    py_paths: list[Path],
    read: Callable[[Path], str],
    sys_path: tuple[Path, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every component and diagnostic in the given ``.pjx`` and ``.py`` files."""
    project = _Project(read, sys_path, py_paths=set(py_paths))

    def guarded(path: Path, work: Callable[[], list[dict[str, Any]]]):
        """``work()``, or what a bug in it becomes: one diagnostic on ``path``."""
        try:
            return work()
        except Exception as error:  # noqa: BLE001
            message = f"{type(error).__name__}: {error}"
            project.report(path, _range(1, 0, 1, 0), "internal-error", message)
            return []

    def load(path: Path) -> list[dict[str, Any]]:
        try:
            source = read(path)
        except (OSError, UnicodeDecodeError) as error:
            project.report(path, _range(1, 0, 1, 0), "unreadable-file", str(error))
            return []
        blocks, errors = scan_blocks(source, str(path))
        for error in errors:
            project.report(path, error["range"], error["code"], error["message"])
        project.documents[path] = _Document(path, source, blocks)
        return []

    def describe_document(document: _Document) -> list[dict[str, Any]]:
        if document.path in project.claimed:
            return []
        if _has_python(document):
            return _python_components(project, document)
        # The same line-start gate as the runtime's: a file with no opener
        # at the start of a line is a template, whatever its comments say.
        if opener_line(document.source) is not None:
            return [_unreadable_python_component(document)]
        if is_component_stem(document.path.stem):
            return [_template_component(project, document)]
        return []

    for path in pjx_paths:
        guarded(path, lambda path=path: load(path))
    project.pjx_dirs = {path.parent for path in project.documents}
    components: list[dict[str, Any]] = []
    for path in py_paths:
        components += guarded(path, lambda path=path: _py_components(project, path))
    for document in list(project.documents.values()):
        components += guarded(
            document.path, lambda document=document: describe_document(document)
        )
    return components, project.diagnostics


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
    diagnostics = []
    for finding in sync(paths, write=False):
        if finding.kind not in advice:
            continue
        orphaned = finding.kind == ORPHANED
        path = finding.path if orphaned else finding.path.with_suffix(".pjx")
        line = 1 if orphaned else opened.get(path.as_posix(), 1)
        # The opener of a document is `{#python`: eight columns.
        where = _range(line, 0, line, 0 if orphaned else len("{#python"))
        diagnostics.append(
            _diagnostic(
                path, where, f"stub-{finding.kind}", advice[finding.kind], "warning"
            )
        )
    return diagnostics


def _builtins_dir() -> Path:
    return _absolute(str(resources.files("pyjinhx").joinpath("builtins")))


def _is_builtin(component: dict[str, Any]) -> bool:
    path = (component["class"] or component["document"])["path"]
    return path.startswith(_builtins_dir().as_posix() + "/")


def _collisions(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A warning on each component whose ``name`` another has too.

    The registry keeps one class per name, and a bare template only answers
    when no class does, so templates and classes are compared among
    themselves. One component saying ``pjx_replace=True`` settles it.
    """
    groups: dict[tuple[str, bool], list[dict[str, Any]]] = {}
    for component in components:
        key = (component["name"], component["kind"] == "template")
        groups.setdefault(key, []).append(component)
    diagnostics = []
    for (name, _), group in groups.items():
        if len(group) < 2 or sum(c["replaces"] for c in group) == 1:
            continue
        for component in group:
            if _is_builtin(component):
                continue
            others = ", ".join(c["id"] for c in group if c is not component)
            where = (component["class"] or {}).get("range") or _range(1, 0, 1, 0)
            path = (component["class"] or component["document"])["path"]
            message = (
                f"{name!r} is also the name of {others}; the registry keeps one "
                "of them. Rename all but one, or mark one pjx_replace=True"
            )
            diagnostics.append(
                _diagnostic(Path(path), where, "tag-collision", message, "warning")
            )
    return diagnostics


def _manifest(
    roots: list[Path], components: list[dict[str, Any]], diagnostics: list[dict]
) -> dict[str, Any]:
    for component in components:
        component["builtin"] = _is_builtin(component)
    components.sort(
        key=lambda c: (
            c["document"]["path"],
            _start(c["class"]["range"]) if c["class"] else (0, 0),
            c["tag"],
        )
    )
    diagnostics.sort(
        key=lambda d: (d["path"], _start(d["range"]), d["code"], d["message"])
    )
    try:
        installed = version("pyjinhx")
    except PackageNotFoundError:
        installed = "unknown"
    return {
        "manifest_version": MANIFEST_VERSION,
        "grammar_version": json.loads(grammar_text())["version"],
        "pyjinhx_version": installed,
        "roots": [root.as_posix() for root in roots],
        "components": components,
        "diagnostics": diagnostics,
    }


def describe(paths: list[Path], sys_path: list[Path] | None = None) -> dict[str, Any]:
    """The manifest of every component under ``paths`` and of the builtins, as
    a JSON-ready dict. ``sys_path`` lists the directories modules are imported
    from, which name them (see `module_name_for`)."""
    roots = [_absolute(p) for p in paths]
    found = walk([*roots, _builtins_dir()], {".pjx", ".py"})
    components, diagnostics = _build(
        found[".pjx"], found[".py"], _read, tuple(map(_absolute, sys_path or []))
    )
    diagnostics += _stub_diagnostics(roots, components)
    diagnostics += _collisions(components)
    return _manifest(roots, components, diagnostics)


def describe_buffer(
    filename: Path, text: str, sys_path: list[Path] | None = None
) -> dict[str, Any]:
    """The manifest entries and diagnostics of one file, as the editor holds it.

    ``text`` stands in for the file on disk, which may not exist or may be
    older. Its neighbours in the same directory are read from disk, because
    whether it is a component depends on them. No stub diagnostics: the
    buffer's stub is a file on disk, and it is the editor's to regenerate.
    """
    file = _absolute(filename)
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    found = walk([_builtins_dir()], {".pjx", ".py"})
    names = {file, *file.parent.glob("*.pjx"), *file.parent.glob("*.py")}
    names |= set(found[".pjx"]) | set(found[".py"])
    pjx = sorted(p for p in names if p.suffix == ".pjx")
    py = sorted(p for p in names if p.suffix == ".py")
    components, diagnostics = _build(
        pjx,
        py,
        lambda path: text if path == file else _read(path),
        tuple(map(_absolute, sys_path or [])),
    )
    diagnostics += _collisions(components)
    shown = file.as_posix()
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
    ``python -m pyjinhx.manifest [--grammar] [--stdin --filename F]
    [--sys-path DIR ...] [paths]``.

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
    parser.add_argument(
        "--sys-path",
        action="append",
        default=[],
        type=Path,
        metavar="DIR",
        help="a directory modules are imported from; repeatable",
    )
    args = parser.parse_args(argv)
    if args.grammar:
        sys.stdout.write(grammar_text())
        return 0
    if args.stdin:
        if args.filename is None:
            parser.error("--stdin needs --filename")
        text = sys.stdin.buffer.read().decode("utf-8", "replace")
        result = describe_buffer(args.filename, text, args.sys_path)
    else:
        missing = [p for p in args.paths if not p.exists()]
        for path in missing:
            print(f"{path}: no such file or directory", file=sys.stderr)
        if missing:
            return 2
        result = describe(args.paths, args.sys_path)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
