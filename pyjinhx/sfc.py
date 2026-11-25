"""Single-file components: reading a class's inline template out of its module.

A component may carry its template as a string instead of an adjacent `.pjx`
file::

    class Badge(BaseComponent):
        label: str

        template = \"\"\"
        <span class="badge">{{ label }}</span>
        \"\"\"

A ``.pjx`` document may also carry its class in a ``{#python ... #}`` block;
`python_block` finds it and `python_source` yields its code.

Import-pure — stdlib only. The module source is parsed, never executed, and
the imported class is never consulted, so a template edited on disk is seen
without re-importing anything.
"""

import ast
import io
import os
import re
import textwrap
import threading
import tokenize
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import NamedTuple

# Jinja's lexer reads left to right, so a ``{#`` is a comment only where it is
# not inside a ``{% raw %}`` region or a ``{{ }}`` / ``{% %}`` tag, whose
# string literals may hold ``{#``, ``#}``, ``}}`` or ``%}``. One alternation
# skips those and leaves comments, which run to the first ``#}``. A tag's
# strings and other characters are disjoint alternatives, so a failed match
# cannot be retried a second way. An opener that is never closed is an error
# in Jinja, so it swallows the rest of the document instead of being rescanned
# from every later position; an unclosed ``{#python`` is matched first so it
# can be reported.
_STRING = r"""'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*\""""
_LEXEME_RE = re.compile(
    r"\{%[-+]?\s*raw\s*[-+]?%\}.*?\{%[-+]?\s*endraw\s*[-+]?%\}"
    r"|\{%[-+]?\s*raw\s*[-+]?%\}.*"
    r"|\{\{(?:" + _STRING + r"|[^'\"])*?\}\}"
    r"|\{%(?:" + _STRING + r"|[^'\"])*?%\}"
    r"|\{#(?P<comment>.*?)#\}"
    r"|(?P<unclosed>\{#python[ \t\r]*(?:\n|\Z))"
    r"|\{[{%#].*",
    re.DOTALL,
)


def comments(source: str) -> Iterator[re.Match[str]]:
    """Every Jinja comment in ``source``; group 1 is its text.

    Reads the default Jinja delimiters only: custom ``*_start_string`` values
    and line statement or line comment prefixes are not recognised. Braces are
    not balanced inside ``{{ }}``, so an expression such as ``{{ {1: {2: 3}} }}``
    ends at its first ``}}`` where Jinja would read on; a comment opener after
    such an expression in the same tag can be missed.
    """
    for match in _LEXEME_RE.finditer(source):
        if match.group("comment") is not None:
            yield match


def strip_to_text(source: str) -> str:
    """``source`` with every comment, tag and raw region replaced by its
    newlines, leaving only the text Jinja renders as written."""
    return _LEXEME_RE.sub(lambda m: "\n" * m.group().count("\n"), source)


def has_markup(source: str) -> bool:
    """Whether ``source`` has anything but comments and whitespace, so that a
    document made only of blocks is told apart from one that renders."""
    return bool("".join(_outside_comments(source)).strip())


def _outside_comments(source: str) -> Iterator[str]:
    position = 0
    for match in comments(source):
        yield source[position : match.start()]
        position = match.end()
    yield source[position:]


# How a class name becomes the file stem its template is found under, and which
# stems are component names; discovery, the component base class and the
# manifest all apply these, so they live in one stdlib-only place.
_PASCAL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SNAKE_CASE_RE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")

# The legacy spaced header, ``{# def ... #}``; only honoured as the first thing
# in the document, where it cannot be mistaken for a prose comment. An inline
# template opens with an empty comment that pads its line numbers to the
# module's, so one may stand before it.
LEGACY_HEADER_RE = re.compile(
    r"\A\s*(?:\{#\s*#\}\s*)?\{#\s*def\s+(?P<sig>.*?)\s*#\}", re.DOTALL
)


def pascal_to_snake(name: str) -> str:
    """Convert a PascalCase/CamelCase identifier to snake_case."""
    return _PASCAL_BOUNDARY_RE.sub("_", name).lower()


def is_component_stem(stem: str) -> bool:
    """Whether ``stem`` is exactly the shape `pascal_to_snake` emits."""
    return _SNAKE_CASE_RE.fullmatch(stem) is not None


# The words that open an inline block: ``{#def``, ``{#css``, ``{#js``, ``{#python``.
BLOCK_KEYWORDS = ("def", "css", "js", "python")

# Stable names for the ways a block is malformed, shared with the block
# grammar's conformance corpus and the editor tooling that reads it.
PYTHON_BLOCK_EARLY_CLOSE = "python-block-early-close"
SECOND_BLOCK = "second-block"
OPENER_NOT_AT_LINE_START = "opener-not-at-line-start"
TEXT_AFTER_CLOSER = "text-after-closer"
CLOSER_NOT_AT_LINE_START = "closer-not-at-line-start"
UNCLOSED_BLOCK = "unclosed-block"
STRAY_COMMENT_CLOSE = "stray-comment-close"


def template_value(node: ast.ClassDef) -> ast.expr | None:
    """The expression a class body assigns to ``template``, or None.

    The last assignment wins, as it does when Python runs the body.
    """
    value = None
    for statement in node.body:
        match statement:
            case ast.Assign(targets=targets) if any(
                isinstance(target, ast.Name) and target.id == "template"
                for target in targets
            ):
                value = statement.value
            case ast.AnnAssign(target=ast.Name(id="template"), value=ast.expr()):
                value = statement.value
    return value


# The last parse of each module, keyed by filename and checked against the
# source it was made from. A template is read several times as its class
# registers and renders, so without this a module of N components is parsed
# N times over. Each entry is built whole and then swapped in under the lock.
_parsed: dict[str, tuple[str, dict[str, list[ast.expr]]]] = {}
_parsed_lock = threading.Lock()


def _templates_in(module_source: str, filename: str) -> dict[str, list[ast.expr]]:
    """Every class in ``module_source`` that assigns ``template``, by class name."""
    with _parsed_lock:
        cached = _parsed.get(filename)
    if cached is not None and cached[0] == module_source:
        return cached[1]
    found: dict[str, list[ast.expr]] = {}
    for node in ast.walk(ast.parse(module_source, filename=filename)):
        if isinstance(node, ast.ClassDef):
            value = template_value(node)
            if value is not None:
                found.setdefault(node.name, []).append(value)
    with _parsed_lock:
        _parsed[filename] = (module_source, found)
    return found


def extract_template(
    module_source: str, class_name: str, filename: str = "<unknown>"
) -> str:
    """The inline template of ``class_name``, as Jinja source.

    Common indentation and blank edges are removed, so the template may be
    indented along with the class body. Every remaining line sits on the same
    line number it has in ``module_source``.

    Raises:
        SyntaxError: ``module_source`` is not valid Python.
        ValueError: No class of that name assigns ``template``, more than one
            does, or the value is anything but one string literal.
    """
    values = _templates_in(module_source, filename).get(class_name, [])
    if not values:
        raise ValueError(
            f"{filename}: class {class_name} has no inline template: its body "
            f"assigns no `template` string."
        )
    if len(values) > 1:
        lines = ", ".join(str(line) for line in sorted(v.lineno for v in values))
        raise ValueError(
            f"{filename}: classes named {class_name} assign `template` on lines "
            f"{lines}. An inline template is found by its class's name, so "
            f"rename one."
        )
    value = values[0]
    match value:
        case ast.Constant(value=str() as text) if is_one_literal(module_source, value):
            body = textwrap.dedent(text)
        case _:
            raise ValueError(
                f"{filename}, line {value.lineno}: {class_name}.template must "
                f"be a plain string literal. It is read from the source text, "
                f"so an f-string, a concatenation or a name cannot be used."
            )
    content = body.lstrip()
    skipped_lines = body[: len(body) - len(content)].count("\n")
    # A Jinja comment renders as nothing but its newlines are still counted,
    # so padding with one makes template line N the module's line N. Errors
    # and tracebacks then point into the .py file with no source map.
    padding = "\n" * (value.lineno - 1 + skipped_lines)
    return f"{{#{padding}#}}{content.rstrip()}"


def is_one_literal(module_source: str, node: ast.expr) -> bool:
    """Whether ``node`` is written as one string, not ``"a" "b"``.

    Python joins adjacent literals into one constant, which would hide the
    line breaks between the pieces from the line-number padding.
    """
    segment = ast.get_source_segment(module_source, node) or ""
    tokens = tokenize.generate_tokens(io.StringIO(segment).readline)
    return sum(token.type == tokenize.STRING for token in tokens) == 1


def read_document(template_path: Path, inline_class: str | None) -> str:
    """The pjx document a component renders: a ``.pjx`` file's text, or the
    inline template of ``inline_class`` read out of the ``.py`` module at
    ``template_path``.

    The one way template source is read, so a ``.py`` module is never
    mistaken for a document.
    """
    # A byte order mark is not part of the document: editors add one, and a
    # header or block opener would no longer start its line.
    source = template_path.read_text(encoding="utf-8-sig")
    if inline_class is None:
        return source
    return extract_template(source, inline_class, str(template_path))


class PythonBlock(NamedTuple):
    """A ``{#python`` block: the 1-based lines of its opener and closer, and
    the body's text. The body spans the lines between them."""

    open_line: int
    close_line: int
    body: str


class BlockSyntaxError(SyntaxError):
    """A malformed block, with the stable ``code`` naming how."""

    def __init__(
        self, code: str, message: str, location: tuple[str, int, int, str]
    ) -> None:
        super().__init__(message, location)
        self.code = code


def python_block(source: str, filename: str) -> PythonBlock | None:
    """The ``{#python ... #}`` block of the document ``source``, or None.

    The opener is a line of exactly ``{#python`` in column 0 (trailing spaces
    and tabs allowed). The closer is the first ``#}``, which must be alone on
    its line in column 0, as Jinja ends the comment there whatever Python
    thinks of it. A ``-#}`` closer is refused: Jinja would eat the line break
    after it.

    Raises:
        BlockSyntaxError: The opener is not at the start of its line or is
            never closed, a second block follows, the first ``#}`` is not
            alone in column 0, or text follows the closer. ``lineno`` is the
            offending line.
    """
    found: PythonBlock | None = None
    for match in _LEXEME_RE.finditer(source):
        if match.group("unclosed"):
            raise _block_error(
                UNCLOSED_BLOCK,
                "this {#python block is never closed by a #}",
                source,
                filename,
                match.start(),
            )
        text = match.group("comment")
        if text is None:
            continue
        rest = text.removeprefix("python")
        if rest == text or not rest.lstrip(" \t\r").startswith("\n"):
            continue
        if found is not None:
            raise _block_error(
                SECOND_BLOCK,
                f"a second {{#python block; the first is on line {found.open_line}, "
                f"and a document holds at most one",
                source,
                filename,
                match.start(),
            )
        if source.rfind("\n", 0, match.start()) + 1 != match.start():
            raise _block_error(
                OPENER_NOT_AT_LINE_START,
                "{#python must start its line, in column 0",
                source,
                filename,
                match.start(),
            )
        found = _closed_block(source, filename, match)
    return found


def _closed_block(source: str, filename: str, match: re.Match[str]) -> PythonBlock:
    """The block ``match`` spans, once its closer is checked to stand alone."""
    close = match.end() - 2
    close_start = source.rfind("\n", 0, close) + 1
    before = source[close_start:close]
    if before and before.strip(" \t") in ("", "-", "+"):
        raise _block_error(
            CLOSER_NOT_AT_LINE_START,
            "the closing `#}` of a {#python block must be alone in column 0",
            source,
            filename,
            close,
        )
    if before:
        raise _block_error(
            PYTHON_BLOCK_EARLY_CLOSE,
            'a "#}" ends the {#python block here, before its closer, which must '
            'be alone on its line; write the pair as "#" "}" (in a string, an '
            "f-string or a comment) or move the code out",
            source,
            filename,
            close,
        )
    line_end = source.find("\n", close)
    line_end = len(source) if line_end == -1 else line_end
    if source[match.end() : line_end].strip(" \t\r"):
        raise _block_error(
            TEXT_AFTER_CLOSER,
            "nothing may follow the #} that closes a {#python block on its line",
            source,
            filename,
            match.end(),
        )
    body_start = source.find("\n", match.start()) + 1
    return PythonBlock(
        source.count("\n", 0, match.start()) + 1,
        source.count("\n", 0, close) + 1,
        source[body_start:close_start],
    )


def _block_error(
    code: str, message: str, source: str, filename: str, position: int
) -> BlockSyntaxError:
    """A `BlockSyntaxError` located at ``position`` in ``source``."""
    line_start = source.rfind("\n", 0, position) + 1
    line_end = source.find("\n", position)
    text = source[line_start : len(source) if line_end == -1 else line_end]
    lineno = source.count("\n", 0, position) + 1
    return BlockSyntaxError(
        code, message, (filename, lineno, position - line_start + 1, text)
    )


def python_source(source: str, filename: str) -> str | None:
    """The Python of the document's ``{#python`` block, or None.

    One newline stands in for each line above the body, so a line or column
    in the compiled code is the same line and column in the file.
    """
    block = python_block(source, filename)
    if block is None:
        return None
    return "\n" * block.open_line + block.body


def module_name_for(path: str | Path, sys_path: Iterable[str] = ()) -> str | None:
    """The dotted module name ``path`` imports under, or ``None`` if it has none.

    Imports nothing and reads no file; it only asks whether ``__init__.py``
    exists in the directories above the file. The name is the path below the
    top of the package chain (the highest directory holding an
    ``__init__.py``). With no ``sys_path``, or when the directory above that
    top is an entry of it, that is the answer. Otherwise the file belongs to a
    namespace package, and the name is the path below the deepest ``sys_path``
    entry that holds it. ``""`` in ``sys_path`` means the working directory.
    Symlinks are kept as spelled, the way the import system sees them, and
    only if nothing matches is the resolved path tried.
    """
    spelled = Path(os.path.abspath(path))
    name = _module_name(spelled, sys_path)
    resolved = spelled.resolve()
    if name is None and resolved != spelled:
        name = _module_name(resolved, sys_path)
    return name


def _module_name(file: Path, sys_path: Iterable[str]) -> str | None:
    entries = [
        Path(os.path.abspath(entry or os.getcwd()))
        for entry in sys_path
        if isinstance(entry, str)
    ]
    top = file.parent
    while (top / "__init__.py").is_file():
        top = top.parent
    if not entries or top in entries:
        base = top
    else:
        holders = [entry for entry in entries if file.is_relative_to(entry)]
        if not holders:
            return None
        base = max(holders, key=lambda entry: len(entry.parts))
    names = file.relative_to(base).with_suffix("").parts
    if names[-1] == "__init__":
        # A package's own file is imported under the package's name.
        names = names[:-1]
    if not names:
        return None
    return ".".join(names) if all(name.isidentifier() for name in names) else None


# What ``ast.literal_eval`` may raise on source text: an unhashable dict key is
# a TypeError, and a deeply nested literal exhausts the parser.
LITERAL_ERRORS = (ValueError, TypeError, SyntaxError, MemoryError, RecursionError)


def dotted_name(node: ast.expr) -> str | None:
    """``node`` as ``a.b.c`` text if it is a pure chain of two or more names."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not parts or not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


def dotted_default(node: ast.expr) -> tuple[str, bool] | None:
    """The import path a header default names and whether it is called, or None.

    ``pkg.mod.NAME`` is ``("pkg.mod.NAME", False)`` and ``pkg.mod.make()`` is
    ``("pkg.mod.make", True)``. A call with arguments names nothing.
    """
    if isinstance(node, ast.Call):
        path = None if node.args or node.keywords else dotted_name(node.func)
    else:
        path = dotted_name(node)
    return None if path is None else (path, isinstance(node, ast.Call))


class HeaderSignatureError(ValueError):
    """A ``{#def#}`` signature that is not a list of simple named props.

    ``syntax`` is the ``SyntaxError`` when it does not parse, and ``node`` the
    offending argument or default when one is to blame, for editors that point
    at it. ``offset`` is where the signature starts in the ``def`` line that
    was parsed.
    """

    def __init__(
        self,
        message: str,
        *,
        syntax: SyntaxError | None = None,
        node: ast.AST | None = None,
    ) -> None:
        super().__init__(message)
        self.syntax = syntax
        self.node = node


HEADER_PREFIX = "def __pjx_props__("


def header_arguments(signature: str) -> list[tuple[ast.arg, ast.expr | None]]:
    """The ``(argument, default)`` pairs of a ``{#def#}`` signature.

    Reads the signature as the arguments of a function, which is all it is,
    and refuses what a header may not hold: ``*args``, ``**kwargs``,
    keyword-only and positional-only arguments, a duplicate name, and a
    default that is not a literal, a dotted name (``pkg.mod.NAME``) or a dotted
    name called with no arguments (``pkg.mod.make()``). Nothing is imported or
    evaluated beyond ``ast.literal_eval``; the positions in the result are
    those of ``HEADER_PREFIX + signature``.

    Raises:
        HeaderSignatureError: The signature is refused.
    """
    try:
        function = ast.parse(f"{HEADER_PREFIX}{signature}): pass").body[0]
    except SyntaxError as exc:
        raise HeaderSignatureError(
            f"invalid {{#def#}} header signature {signature!r}: {exc.msg}", syntax=exc
        ) from exc
    assert isinstance(function, ast.FunctionDef)
    arguments = function.args
    if (
        arguments.vararg
        or arguments.kwarg
        or arguments.kwonlyargs
        or arguments.posonlyargs
    ):
        raise HeaderSignatureError(
            f"{{#def#}} header may only use simple named props: {signature!r}",
            node=arguments.vararg
            or arguments.kwarg
            or (arguments.kwonlyargs or arguments.posonlyargs)[0],
        )
    args = arguments.args
    # Defaults bind to the *last* N params.
    defaults: list[ast.expr | None] = [None] * (len(args) - len(arguments.defaults))
    defaults += arguments.defaults
    seen: set[str] = set()
    for arg, default in zip(args, defaults, strict=True):
        if arg.arg in seen:
            raise HeaderSignatureError(
                f"{{#def#}} header has duplicate prop {arg.arg!r}", node=arg
            )
        seen.add(arg.arg)
        if default is None:
            continue
        try:
            ast.literal_eval(default)
        except LITERAL_ERRORS:
            if dotted_default(default) is None:
                raise HeaderSignatureError(
                    f"{{#def#}} header default for {arg.arg!r} must be a literal, "
                    "a dotted name (pkg.mod.NAME) or a dotted name called with no "
                    f"arguments (pkg.mod.make()): {ast.unparse(default)!r}",
                    node=default,
                ) from None
    return list(zip(args, defaults, strict=True))
