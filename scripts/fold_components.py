"""Fold pyjinhx components into fewer files.

Three one-way migrations, each a dry run unless ``--write`` is given:

    assets    fold a sibling .css / .js into a {#css#} / {#js#} block
    template  fold a class's adjacent .pjx into ``template = r\"\"\"...\"\"\"``
    declass   turn a fields-only class into a {#def#} header, deleting the .py

    uv run python scripts/fold_components.py assets app/components
    uv run python scripts/fold_components.py template app/components --write

Every run prints a unified diff and a summary, only touches files under the
paths it is given, and exits 1 if it refused anything, after processing the
rest. Running it again finds nothing left to fold.
"""

import argparse
import ast
import difflib
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import TemplateSyntaxError

from pyjinhx._component import _pascal_to_snake
from pyjinhx.sfc import extract_template
from pyjinhx.template_blocks import find_block

_SKIPPED_DIRS = {"__pycache__", "node_modules"}


@dataclass
class Plan:
    """What a subcommand would do: new text per file (None deletes it)."""

    files: dict[Path, str | None] = field(default_factory=dict)
    refusals: list[str] = field(default_factory=list)
    folded: int = 0

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
            parts = candidate.relative_to(path).parts if path.is_dir() else ()
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


def template_value(node: ast.ClassDef) -> ast.stmt | None:
    """The class body's last ``template = ...`` statement, or None."""
    found = None
    for statement in node.body:
        match statement:
            case ast.Assign(targets=[ast.Name(id="template")]):
                found = statement
            case ast.AnnAssign(target=ast.Name(id="template"), value=ast.expr()):
                found = statement
    return found


def assigns_template(node: ast.ClassDef) -> bool:
    return template_value(node) is not None


def base_names(node: ast.ClassDef) -> list[str]:
    return [
        b.id if isinstance(b, ast.Name) else b.attr
        for b in node.bases
        if isinstance(b, ast.Name | ast.Attribute)
    ]


def has_own_template(module: Module, node: ast.ClassDef) -> bool:
    pjx = module.path.parent / f"{_pascal_to_snake(node.name)}.pjx"
    return assigns_template(node) or pjx.is_file()


def has_block(text: str, kind: str, path: Path) -> bool:
    try:
        return find_block(text, kind, str(path)) is not None
    except TemplateSyntaxError:
        return True


def block_text(kind: str, body: str, indent: str = "") -> str:
    lines = [f"{{#{kind}", *body.strip().splitlines(), "#}"]
    return "\n".join(indent + line if line else line for line in lines) + "\n"


# --- assets -----------------------------------------------------------------


def inherited_by(asset_stem: str, modules: list[Module]) -> str | None:
    """A subclass with its own template of the class that owns ``asset_stem``."""
    owners = {
        n.name
        for m in modules
        for n in m.classes()
        if _pascal_to_snake(n.name) == asset_stem
    }
    for module in modules:
        for node in module.classes():
            if owners & set(base_names(node)) and has_own_template(module, node):
                return node.name
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
    statement = template_value(node)
    literal = (
        statement.value if isinstance(statement, ast.Assign | ast.AnnAssign) else None
    )
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
            if _pascal_to_snake(node.name) == stem and assigns_template(node):
                return module.path, node.name
    return pjx, None


def fold_assets(paths: list[Path]) -> Plan:
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
        if subclass := inherited_by(asset.stem, modules):
            plan.refuse(asset, f"{subclass} inherits it and has a template of its own")
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
            pjx = module.path.parent / f"{_pascal_to_snake(node.name)}.pjx"
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


def finish(name: str, plan: Plan, write: bool) -> int:
    """Print the plan's diffs, apply it if ``write``, and return the exit code."""
    for path, new in sorted(plan.files.items()):
        old = path.read_text(encoding="utf-8") if path.exists() else None
        print(diff(path, old, new), end="")
        if write:
            if new is None:
                path.unlink()
            else:
                path.write_text(new, encoding="utf-8")
    for refusal in plan.refusals:
        print(f"refused {refusal}")
    mode = "written" if write else "dry run, nothing written; pass --write"
    print(f"{name}: {plan.folded} folded, {len(plan.refusals)} refused ({mode})")
    return 1 if plan.refusals else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("assets", "template", "declass"):
        command = commands.add_parser(name)
        command.add_argument("paths", nargs="+", type=Path)
        command.add_argument("--write", action="store_true", help="apply the changes")
    args = parser.parse_args(argv)
    plan = {"assets": fold_assets, "template": fold_template}[args.command](args.paths)
    return finish(args.command, plan, args.write)


if __name__ == "__main__":
    sys.exit(main())
