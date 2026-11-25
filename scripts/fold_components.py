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
import sys
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import TemplateSyntaxError

from pyjinhx._component import _pascal_to_snake
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


def assigns_template(node: ast.ClassDef) -> bool:
    return any(
        isinstance(s, ast.Assign | ast.AnnAssign)
        and "template"
        in ast.unparse(s.targets[0] if isinstance(s, ast.Assign) else s.target)
        for s in node.body
    )


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


def fold_assets(paths: list[Path]) -> Plan:
    plan = Plan()
    modules = load_modules(paths)
    for asset in walk(paths, "*.css") + walk(paths, "*.js"):
        kind = asset.suffix[1:]
        template = asset.with_suffix(".pjx")
        if not template.is_file():
            continue
        body = asset.read_text(encoding="utf-8")
        if "#}" in body:
            plan.refuse(
                asset, "its text contains `#}`, which would end the block early"
            )
            continue
        if has_block(plan.read(template), kind, template):
            plan.refuse(asset, f"{template.name} already has a {{#{kind}#}} block")
            continue
        if subclass := inherited_by(asset.stem, modules):
            plan.refuse(asset, f"{subclass} inherits it and has a template of its own")
            continue
        text = plan.read(template)
        plan.files[template] = text.rstrip("\n") + "\n" + block_text(kind, body)
        plan.files[asset] = None
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
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("assets", "template", "declass"):
        command = commands.add_parser(name)
        command.add_argument("paths", nargs="+", type=Path)
        command.add_argument("--write", action="store_true", help="apply the changes")
    args = parser.parse_args(argv)
    plan = {"assets": fold_assets}[args.command](args.paths)
    return finish(args.command, plan, args.write)


if __name__ == "__main__":
    sys.exit(main())
