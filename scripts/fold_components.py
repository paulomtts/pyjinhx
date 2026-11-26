"""Fold pyjinhx components into fewer files.

Four one-way migrations, each a dry run unless ``--write`` is given:

    assets    fold a sibling .css / .js into a {#css#} / {#js#} block
    template  fold a class's adjacent .pjx into ``template = r\"\"\"...\"\"\"``
    declass   turn a fields-only class into a {#def#} header, deleting the .py
    pyblock   move a class's module into a {#python block at the top of its .pjx

    uv run python scripts/fold_components.py assets app/components
    uv run python scripts/fold_components.py template app/components --write

Every run prints a unified diff and a summary, only touches files under the
paths it is given, and exits 1 if it refused anything, after processing the
rest. Running it again finds nothing left to fold.
"""

import argparse
import ast
import difflib
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import TemplateSyntaxError

from pyjinhx.components.props_header import parse_props_header
from pyjinhx.document.scanner import (
    BlockSyntaxError,
    extract_template,
    has_markup,
    opener_line,
    package_root,
    pascal_to_snake,
    python_block,
    template_value,
)
from pyjinhx.document.template_blocks import find_block, find_header

_SKIPPED_DIRS = {"__pycache__", "node_modules"}


@dataclass
class Plan:
    """What a subcommand would do: new text per file (None deletes it)."""

    files: dict[Path, str | None] = field(default_factory=dict)
    refusals: list[str] = field(default_factory=list)
    folded: int = 0
    notes: list[str] = field(default_factory=list)
    reminders: list[str] = field(default_factory=list)

    def read(self, path: Path) -> str:
        pending = self.files.get(path)
        return pending if pending is not None else path.read_text(encoding="utf-8")

    def refuse(self, path: Path, reason: str) -> None:
        self.refusals.append(f"{path}: {reason}")


def walk(paths: list[Path], pattern: str) -> list[Path]:
    """Files matching ``pattern`` under ``paths``, sorted, hidden dirs skipped."""
    found: set[Path] = set()
    for path in paths:
        candidates = [path] if path.is_file() else path.rglob(pattern)
        for candidate in candidates:
            # Directories only: a hidden file such as .coveragerc is still a file.
            parts = candidate.relative_to(path).parts[:-1] if path.is_dir() else ()
            if any(p.startswith(".") or p in _SKIPPED_DIRS for p in parts):
                continue
            if candidate.match(pattern):
                found.add(candidate)
    return sorted(found)


@dataclass
class Module:
    """A parsed Python file."""

    path: Path
    source: str
    tree: ast.Module

    def classes(self) -> list[ast.ClassDef]:
        return [n for n in self.tree.body if isinstance(n, ast.ClassDef)]


def load_modules(paths: list[Path]) -> list[Module]:
    modules = []
    for path in walk(paths, "*.py"):
        source = path.read_text(encoding="utf-8")
        try:
            modules.append(Module(path, source, ast.parse(source)))
        except SyntaxError:
            continue
    return modules


def assigns_template(node: ast.ClassDef) -> bool:
    return template_value(node) is not None


def base_names(node: ast.ClassDef) -> list[str]:
    return [
        b.id if isinstance(b, ast.Name) else b.attr
        for b in node.bases
        if isinstance(b, ast.Name | ast.Attribute)
    ]


def has_own_template(module: Module, node: ast.ClassDef) -> bool:
    pjx = module.path.parent / f"{pascal_to_snake(node.name)}.pjx"
    return assigns_template(node) or pjx.is_file()


def has_block(text: str, kind: str, path: Path) -> bool:
    try:
        return find_block(text, kind, str(path)) is not None
    except TemplateSyntaxError:
        return True


def has_header(text: str, path: Path) -> bool:
    try:
        return find_header(text, str(path)) is not None
    except TemplateSyntaxError:
        return True


def block_text(kind: str, body: str, indent: str = "") -> str:
    lines = [f"{{#{kind}", *body.strip().splitlines(), "#}"]
    return "\n".join(indent + line if line else line for line in lines) + "\n"


# --- assets -----------------------------------------------------------------


def references(
    name: str, roots: list[Path], skip: Path, pattern: str = "*.py"
) -> list[str]:
    """``path:line: text`` for every line in ``pattern`` files under ``roots`` that mentions ``name``.

    Matches the file's name only; a dotted module name is not reported, since
    an import of it keeps working after a fold that leaves the name unchanged.
    """
    found = []
    mention = re.compile(rf"\b{re.escape(name)}\b")
    for path in walk(roots, pattern):
        if path == skip or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        found += [
            f"{path}:{number}: {line.strip()}"
            for number, line in enumerate(lines, 1)
            if mention.search(line)
        ]
    return found


def subclass_refusal(asset_stem: str, kind: str, modules: list[Module]) -> str | None:
    """Why a subclass of the class owning ``asset_stem`` blocks the fold, or None.

    A subclass with its own template stops seeing a block in the parent's. One
    that inherits the template but has its own sibling file of this kind would
    start shipping the block beside that file, which used to shadow the parent's.
    """
    owners = {
        n.name
        for m in modules
        for n in m.classes()
        if pascal_to_snake(n.name) == asset_stem
    }
    for module in modules:
        for node in module.classes():
            if not owners & set(base_names(node)):
                continue
            if has_own_template(module, node):
                return f"{node.name} inherits it and has a template of its own"
            sibling = module.path.parent / f"{pascal_to_snake(node.name)}.{kind}"
            if sibling.is_file():
                return (
                    f"{node.name} inherits the template and has its own {sibling.name}"
                )
    return None


def offset(lines: list[str], lineno: int, column: int) -> int:
    """Character offset of an ``ast`` position (its column counts UTF-8 bytes)."""
    line = lines[lineno - 1]
    return sum(map(len, lines[: lineno - 1])) + len(line.encode()[:column].decode())


def add_inline_block(source: str, class_name: str, kind: str, body: str) -> str:
    """``source`` with a block added inside ``class_name``'s template string.

    Raises ValueError saying why the string cannot take it.
    """
    tree = ast.parse(source)
    node = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name
    )
    literal = template_value(node)
    if not (isinstance(literal, ast.Constant) and isinstance(literal.value, str)):
        raise ValueError("the template is not a plain string literal")  # noqa: TRY004
    lines = source.splitlines(keepends=True)
    start = offset(lines, literal.lineno, literal.col_offset)
    end = offset(
        lines, literal.end_lineno or literal.lineno, literal.end_col_offset or 0
    )
    written = source[start:end]
    quote = written[-3:]
    if quote not in ('"""', "'''") or not written.lstrip("rRbBuU").startswith(quote):
        raise ValueError("the template is not a triple-quoted string")
    if quote in body:
        raise ValueError(f"its text contains {quote}")
    if "\\" in body and "r" not in written[:3].lower():
        raise ValueError(
            "its text has a backslash and the template is not a raw string"
        )
    inside = source[start : end - 3]
    kept = inside.rstrip(" \t")
    if kept.endswith("\n"):
        # The closing quotes sit on their own line: the block goes above them.
        indent = inside[len(kept) :]
    else:
        kept, indent = inside + "\n", " " * node.body[0].col_offset
    block = block_text(kind, body, indent)
    return source[:start] + kept + block + indent + quote + source[end:]


def locate_template(
    stem: str, modules: list[Module], directory: Path
) -> tuple[Path, str | None]:
    """The template ``<stem>.<kind>`` sits beside: a .pjx, or a class's string."""
    pjx = directory / f"{stem}.pjx"
    if pjx.is_file():
        return pjx, None
    for module in modules:
        if module.path.parent != directory:
            continue
        for node in module.classes():
            if pascal_to_snake(node.name) == stem and assigns_template(node):
                return module.path, node.name
    return pjx, None


def fold_assets(paths: list[Path], roots: list[Path] | None = None) -> Plan:
    plan = Plan()
    modules = load_modules(paths)
    for asset in walk(paths, "*.css") + walk(paths, "*.js"):
        kind = asset.suffix[1:]
        target, class_name = locate_template(asset.stem, modules, asset.parent)
        if not target.is_file():
            continue
        body = asset.read_text(encoding="utf-8")
        text = plan.read(target)
        if "#}" in body:
            plan.refuse(
                asset, "its text contains `#}`, which would end the block early"
            )
            continue
        if reason := subclass_refusal(asset.stem, kind, modules):
            plan.refuse(asset, reason)
            continue
        if class_name is None:
            existing = text
        else:
            try:
                existing = extract_template(text, class_name)
            except (SyntaxError, ValueError) as exc:
                plan.refuse(asset, str(exc))
                continue
        if has_block(existing, kind, target):
            plan.refuse(asset, f"{target.name} already has a {{#{kind}#}} block")
            continue
        if class_name is None:
            plan.files[target] = text.rstrip("\n") + "\n" + block_text(kind, body)
        else:
            try:
                plan.files[target] = add_inline_block(text, class_name, kind, body)
            except ValueError as exc:
                plan.refuse(asset, str(exc))
                continue
        plan.files[asset] = None
        plan.folded += 1
        # Code that names the file by path breaks once it is gone.
        plan.notes += [
            f"{asset.name} is still named: {line}"
            for line in references(asset.name, roots or paths, asset, "*")
        ]
    return plan


# --- template ---------------------------------------------------------------


def template_refusal(content: str) -> str | None:
    """Why ``content`` cannot sit in a raw triple-quoted string, or None."""
    if '"""' in content and "'''" in content:
        return "it contains both triple-quote styles, so no raw string can hold it"
    if content.rstrip().endswith("\\"):
        return "it ends with a backslash, which would escape the closing quotes"
    return None


def template_statement(content: str, indent: str) -> str:
    quote = "'''" if '"""' in content else '"""'
    lines = content.strip("\n").splitlines()
    body = [indent + line if line.strip() else "" for line in lines]
    return "\n".join([f"{indent}template = r{quote}", *body, f"{indent}{quote}"]) + "\n"


def with_template(source: str, node: ast.ClassDef, content: str) -> str:
    """``module``'s source with ``content`` added as ``node``'s last statement."""
    lines = source.splitlines(keepends=True)
    first = node.body[0]
    indent = " " * first.col_offset
    statement = template_statement(content, indent)
    only = node.body[0] if len(node.body) == 1 else None
    if isinstance(only, ast.Pass) or (
        isinstance(only, ast.Expr)
        and isinstance(only.value, ast.Constant)
        and only.value.value is Ellipsis
    ):
        lines[only.lineno - 1 : only.end_lineno] = [statement]
    else:
        lines.insert(node.end_lineno or node.lineno, "\n" + statement)
    return "".join(lines)


def round_trips(source: str, class_name: str, content: str) -> str | None:
    """A reason the inline template would read back differently, or None."""
    try:
        read = extract_template(source, class_name)
    except (SyntaxError, ValueError) as exc:
        return str(exc)
    if re.sub(r"\A\{#\n*#\}", "", read) != content.strip():
        return "the indentation would change when the template is dedented"
    return None


def folded_template(
    source: str, node: ast.ClassDef, content: str, same_name: int
) -> tuple[str | None, str | None]:
    """``(new source, None)`` for a fold that reads back unchanged, else ``(None, why)``."""
    if same_name > 1:
        return None, f"more than one class named {node.name} in this module"
    if assigns_template(node):
        return None, f"{node.name} already assigns `template`"
    if node.body[0].lineno == node.lineno:
        return None, f"{node.name} has its body on the class line"
    if reason := template_refusal(content):
        return None, reason
    folded = with_template(source, node, content)
    return (
        (folded, None)
        if not (why := round_trips(folded, node.name, content))
        else (None, why)
    )


def fold_template(paths: list[Path]) -> Plan:
    plan = Plan()
    for module in load_modules(paths):
        names = Counter(
            n.name for n in ast.walk(module.tree) if isinstance(n, ast.ClassDef)
        )
        # Last class first, so the line numbers of the ones above stay true.
        for node in reversed(module.classes()):
            pjx = module.path.parent / f"{pascal_to_snake(node.name)}.pjx"
            if not node.bases or not pjx.is_file() or pjx in plan.files:
                continue
            content = pjx.read_text(encoding="utf-8")
            folded, reason = folded_template(
                plan.read(module.path), node, content, names[node.name]
            )
            if folded is None:
                plan.refuse(pjx, reason or "")
                continue
            plan.files[module.path] = folded
            plan.files[pjx] = None
            plan.folded += 1
    return plan


# --- declass ----------------------------------------------------------------

# Names a header reads bare, without an import path.
_HEADER_TYPES = {
    "str", "int", "float", "bool", "list", "dict", "tuple", "Any", "Slot", "Children",
    "ExtraAttrs", "AttrValue", "Optional", "Literal",
}  # fmt: skip
_BARE_ORIGINS = ("pyjinhx", "typing")


def import_paths(tree: ast.Module) -> dict[str, str]:
    """Each imported name mapped to the dotted path it stands for."""
    paths: dict[str, str] = {}
    for node in tree.body:
        match node:
            case ast.Import():
                for alias in node.names:
                    paths[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0]
                    )
            case ast.ImportFrom():
                prefix = "." * node.level + (node.module or "")
                for alias in node.names:
                    paths[alias.asname or alias.name] = f"{prefix}.{alias.name}"
    return paths


def dotted(node: ast.expr, imports: dict[str, str], what: str) -> str:
    """``node`` (a name or ``a.b.c``) with its first name replaced by its import path."""
    root = node
    while isinstance(root, ast.Attribute):
        root = root.value
    if not isinstance(root, ast.Name) or root.id not in imports:
        raise ValueError(
            f"{what} `{ast.unparse(node)}` is not imported, so a header cannot name it"
        )
    path = imports[root.id]
    if path.startswith("."):
        raise ValueError(
            f"{what} `{ast.unparse(node)}` is a relative import, which a header cannot name"
        )
    return path + ast.unparse(node)[len(root.id) :]


def header_type(node: ast.expr, imports: dict[str, str]) -> str:
    """An annotation as header text, import paths spelled out."""
    match node:
        case ast.Constant(value=None):
            return "None"
        case ast.Constant(value=str()):
            raise ValueError("a string annotation is not expressible in a header")
        case ast.Name(id="object") if "object" not in imports:
            return "Any"  # both accept any value; a header spells it Any
        case ast.Name(id=name) if name in _HEADER_TYPES and (
            name not in imports or imports[name].split(".")[0] in _BARE_ORIGINS
        ):
            return name
        case ast.Name() | ast.Attribute():
            return dotted(node, imports, "annotation")
        case ast.BinOp(left=left, op=ast.BitOr(), right=right):
            return f"{header_type(left, imports)} | {header_type(right, imports)}"
        case ast.Subscript(value=ast.Name(id="Literal")):
            members = (
                node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            )
            return f"Literal[{', '.join(map(ast.unparse, members))}]"
        case ast.Subscript(
            value=ast.Name(id="list" | "dict" | "tuple" | "Optional" as head)
        ):
            members = (
                node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            )
            written = [
                "..."
                if head == "tuple"
                and isinstance(m, ast.Constant)
                and m.value is Ellipsis
                else header_type(m, imports)
                for m in members
            ]
            return f"{head}[{', '.join(written)}]"
    raise ValueError(f"annotation `{ast.unparse(node)}` is not expressible in a header")


def header_default(node: ast.expr, imports: dict[str, str]) -> str:
    try:
        ast.literal_eval(node)
    except (ValueError, SyntaxError):
        pass
    else:
        return ast.unparse(node)
    match node:
        case ast.Name() | ast.Attribute():
            return dotted(node, imports, "default")
        case ast.Call(
            func=ast.Name(id="Field"),
            args=[],
            keywords=[ast.keyword(arg="default_factory", value=factory)],
        ):
            # A header copies a literal default per instance, so the two
            # builtin factories are just their empty literals.
            if isinstance(factory, ast.Name) and factory.id in ("dict", "list"):
                return "{}" if factory.id == "dict" else "[]"
            return dotted(factory, imports, "default") + "()"
        case ast.Call(func=ast.Name(id="Field")):
            raise ValueError(
                f"`{ast.unparse(node)}` sets constraints or options, which a "
                "header cannot express"
            )
        case ast.Call():
            raise ValueError(
                f"default `{ast.unparse(node)}` is called once, when the class is "
                "defined; a header would call it for every instance"
            )
    raise ValueError(
        f"default `{ast.unparse(node)}` is not a literal or an importable name"
    )


def class_props(node: ast.ClassDef, imports: dict[str, str]) -> list[str]:
    """The ``{#def#}`` entries for a fields-only class; ValueError says why not."""
    if node.keywords or node.decorator_list:
        raise ValueError(f"{node.name} has class keywords or decorators")
    if base_names(node) != ["BaseComponent"] or len(node.bases) != 1:
        raise ValueError(f"{node.name} has bases other than BaseComponent")
    props, required_id = [], False
    for index, statement in enumerate(node.body):
        match statement:
            case ast.Expr(value=ast.Constant(value=str())) if index == 0:
                pass
            case ast.Pass():
                pass
            case ast.Assign(
                targets=[ast.Name(id="auto_id")], value=ast.Constant(value=value)
            ):
                required_id = required_id or value is False
            case ast.AnnAssign(
                target=ast.Name(id=name), annotation=annotation, value=value
            ):
                entry = f"{name}: {header_type(annotation, imports)}"
                if name == "id" and (value is not None or entry != "id: str"):
                    raise ValueError("`id` may only be declared as a required str")
                props.append(
                    entry + (f" = {header_default(value, imports)}" if value else "")
                )
            case ast.FunctionDef() | ast.AsyncFunctionDef():
                raise ValueError(
                    f"{node.name} defines {statement.name}(), which needs a class"
                )
            case ast.Assign(targets=[ast.Name(id=name)]):
                raise ValueError(f"{node.name} assigns {name}, which needs a class")
            case _:
                raise ValueError(
                    f"{node.name} has a {type(statement).__name__} statement, which needs a class"
                )
    if required_id and not any(p.startswith("id:") for p in props):
        props.insert(0, "id: str")
    return props


def only_the_class(module: Module, node: ast.ClassDef) -> str | None:
    """Why the module holds more than imports and ``node``, or None."""
    for statement in module.tree.body:
        if statement is node or isinstance(statement, ast.Import | ast.ImportFrom):
            continue
        if isinstance(statement, ast.Expr) and isinstance(
            statement.value, ast.Constant
        ):
            continue
        return f"the module also has a {type(statement).__name__} (line {statement.lineno})"
    return None


def header_text(props: list[str]) -> str:
    one_line = f"{{#def {', '.join(props)} #}}"
    if len(one_line) <= 88:
        return one_line
    return "{#def " + ",\n      ".join(props) + " #}"


def subclasses(name: str, modules: list[Module]) -> list[str]:
    """``path:line: Class`` for each class in ``modules`` that has ``name`` as a base."""
    return [
        f"{module.path}:{node.lineno}: {node.name}"
        for module in modules
        for node in ast.walk(module.tree)
        if isinstance(node, ast.ClassDef) and name in base_names(node)
    ]


def fold_declass(paths: list[Path], roots: list[Path] | None = None) -> Plan:
    plan = Plan()
    searched = load_modules([*paths, *(roots or [])])
    for module in load_modules(paths):
        for node in module.classes():
            if module.path.name == "__init__.py" or not node.bases:
                continue
            pjx = module.path.parent / f"{pascal_to_snake(node.name)}.pjx"
            try:
                if not pjx.is_file():
                    raise ValueError(f"there is no {pjx.name} beside it")
                if assigns_template(node):
                    raise ValueError(f"{node.name} assigns its own `template`")
                text = pjx.read_text(encoding="utf-8")
                if has_header(text, pjx):
                    raise ValueError(f"{pjx.name} already has a {{#def#}} header")
                props = class_props(node, import_paths(module.tree))
                if reason := only_the_class(module, node):
                    raise ValueError(reason)
                if found := subclasses(node.name, searched):
                    # Without a class there is nothing for them to import.
                    raise ValueError(
                        f"{node.name} is subclassed, and a header-only component "
                        f"has no importable class: {'; '.join(found)}"
                    )
                if props:
                    header = header_text(props)
                    parse_props_header(header)
                    text = header + "\n" + text
            except ValueError as exc:
                plan.refuse(module.path, str(exc))
                continue
            plan.files[pjx] = text
            plan.files[module.path] = None
            plan.folded += 1
            plan.notes += [
                f"{node.name} is still referenced: {line}"
                for line in references(node.name, roots or paths, module.path)
            ]
    return plan


# --- pyblock ----------------------------------------------------------------


def block_document(source: str, pjx: Path, text: str) -> str:
    """``text`` with ``source`` as a ``{#python`` block above it; ValueError says
    why the result would not read back as that module and that markup."""
    if "#}" in source:
        line = next(n for n, row in enumerate(source.splitlines(), 1) if "#}" in row)
        raise ValueError(
            f"its source has `#}}` on line {line}, which would end the block"
        )
    body = source if source.endswith("\n") else source + "\n"
    document = "{#python\n" + body + "#}\n" + text
    try:
        block = python_block(document, str(pjx))
    except BlockSyntaxError as exc:
        raise ValueError(f"the block would not parse: {exc.msg}") from exc
    if block is None or block.body != body:
        raise ValueError("the block would not read back as the module's source")
    if document.split("\n", block.close_line)[-1] != text:
        raise ValueError("the markup after the block would not read back unchanged")
    return document


def stem_classes(module: Module) -> list[ast.ClassDef]:
    """The classes in ``module`` named for its file, as a document's class is."""
    return [
        n
        for n in module.classes()
        if n.bases and pascal_to_snake(n.name) == module.path.stem
    ]


def read_pjx(pjx: Path) -> str:
    """The text of ``pjx`` without a byte order mark, which would otherwise end
    up in the middle of the folded document."""
    return pjx.read_text(encoding="utf-8-sig")


def pyblock_document(module: Module, pjx: Path) -> str:
    """The new text of ``pjx`` holding ``module``; ValueError says why not."""
    stem = module.path.stem
    if stem == "__init__":
        raise ValueError("a package `__init__.py` cannot hold a document")
    named = stem_classes(module)
    if not named:
        raise ValueError(f"no class named for {stem}")
    if len(named) > 1:
        raise ValueError(f"{stem} names more than one class")
    if assigns_template(named[0]):
        raise ValueError(
            f"{named[0].name} assigns its own `template`; fold it to a file first"
        )
    if not pjx.is_file():
        raise ValueError(f"there is no {pjx.name} beside it (inherited or missing)")
    if (pjx.parent / stem).is_dir():
        raise ValueError(f"a {stem}/ directory would shadow {pjx.name}")
    text = read_pjx(pjx)
    if opener_line(text) is not None:
        raise ValueError(already_has_block(module, pjx, text))
    if has_header(text, pjx):
        raise ValueError(f"{pjx.name} already has a {{#def#}} header")
    if not has_markup(text):
        raise ValueError(f"{pjx.name} has no markup, which a document needs")
    return block_document(module.source, pjx, text)


def already_has_block(module: Module, pjx: Path, text: str) -> str:
    """The refusal for a ``.pjx`` that holds a block: a finished fold, or a
    different module."""
    try:
        block = python_block(text, str(pjx))
    except BlockSyntaxError:
        block = None
    if block and block.body.rstrip("\n") == module.source.rstrip("\n"):
        return f"already folded; delete {module.path.name}"
    return f"{pjx.name} already has a {{#python block"


def needs_pyjinhx_import(path: Path) -> str | None:
    """A reminder when nothing is known to import pyjinhx before the module at
    ``path``: the top package's ``__init__.py`` should, found as
    `scanner.module_name_for` finds it."""
    top = package_root(path.parent)
    if top is None:
        return (
            "something must import pyjinhx before this module is imported "
            f"({path.name} is not in a package)"
        )
    init = (top / "__init__.py").read_text(encoding="utf-8", errors="replace")
    if re.search(r"^\s*(import pyjinhx|from pyjinhx)\b", init, re.MULTILINE):
        return None
    return f"{top / '__init__.py'} needs `import pyjinhx`"


def read_module(path: Path) -> Module | None:
    """``path`` as a `Module`, or None if it is not readable Python."""
    try:
        source = path.read_text(encoding="utf-8-sig")
        return Module(path, source, ast.parse(source))
    except (SyntaxError, UnicodeDecodeError):
        return None


def fold_pyblock(paths: list[Path], roots: list[Path] | None = None) -> Plan:
    plan = Plan()
    given = set(paths)
    for path in walk(paths, "*.py"):
        pjx = path.with_suffix(".pjx")
        module = read_module(path)
        if module is None:
            if path in given:
                plan.refuse(path, "it is not valid Python")
            continue
        # A walk leaves alone the modules that are no document's; one named
        # on the command line is asked about.
        if path not in given and not (stem_classes(module) and pjx.is_file()):
            continue
        try:
            plan.files[pjx] = pyblock_document(module, pjx)
        except ValueError as exc:
            plan.refuse(path, str(exc))
            continue
        plan.files[path] = None
        plan.folded += 1
        plan.notes += [
            f"{path.name} is still named: {line}"
            for line in references(path.name, roots or paths, path, "*")
        ]
        for node in module.classes():
            other = pjx.with_name(pascal_to_snake(node.name) + ".pjx")
            if other != pjx and other.is_file():
                plan.notes.append(f"{node.name} keeps its {other.name}")
        if re.search(r"\b__(file|main)__\b", module.source):
            plan.notes.append(
                f"{path.name} mentions __file__ or __main__: __file__ becomes "
                f"{pjx.name}, and `python {path.name}` stops working"
            )
        if reminder := needs_pyjinhx_import(path):
            plan.reminders.append(reminder)
    return plan


# --- output -----------------------------------------------------------------


def diff(path: Path, old: str | None, new: str | None) -> str:
    return "".join(
        difflib.unified_diff(
            (old or "").splitlines(keepends=True),
            (new or "").splitlines(keepends=True),
            fromfile=str(path) if old is not None else "/dev/null",
            tofile=str(path) if new is not None else "/dev/null",
        )
    )


def write_atomically(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` through a temporary file, so a crash leaves
    the old file or the new one, never half of it."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def finish(name: str, plan: Plan, write: bool) -> int:
    """Print the plan's diffs, apply it if ``write``, and return the exit code."""
    for path, new in sorted(plan.files.items()):
        old = path.read_text(encoding="utf-8") if path.exists() else None
        print(diff(path, old, new), end="")
        if write:
            if new is None:
                path.unlink()
            else:
                write_atomically(path, new)
    for note in plan.notes:
        print(f"reference {note}")
    for refusal in plan.refusals:
        print(f"refused {refusal}")
    for reminder in dict.fromkeys(plan.reminders):
        print(f"remember: {reminder}")
    if name == "pyblock" and plan.folded:
        print("remember: run `python -m pyjinhx.stubgen` to regenerate the stubs")
    mode = "written" if write else "dry run, nothing written; pass --write"
    print(
        f"{name}: {plan.folded} folded, {len(plan.refusals)} refused, "
        f"{len(plan.notes)} references ({mode})"
    )
    return 1 if plan.refusals else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("assets", "template", "declass", "pyblock"):
        command = commands.add_parser(name)
        command.add_argument("paths", nargs="+", type=Path)
        command.add_argument("--write", action="store_true", help="apply the changes")
    for name in ("assets", "declass", "pyblock"):
        commands.choices[name].add_argument(
            "--root",
            action="append",
            type=Path,
            help="where to look for references to what is folded (default: the paths)",
        )
    args = parser.parse_args(argv)
    if args.command == "declass":
        plan = fold_declass(args.paths, args.root)
    elif args.command == "pyblock":
        plan = fold_pyblock(args.paths, args.root)
    elif args.command == "assets":
        plan = fold_assets(args.paths, args.root)
    else:
        plan = fold_template(args.paths)
    return finish(args.command, plan, args.write)


if __name__ == "__main__":
    sys.exit(main())
