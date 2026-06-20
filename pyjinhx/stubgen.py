"""Generate signature-only `.pyi` stubs for `.pjx` single-file components.

Stubs let a type checker resolve ``from app.components.counter import Counter``
in ordinary `.py` files. They are generated into a gitignored ``.pjx/stubs/``
cache mirroring the import path and are never hand-edited.
"""
import argparse
import ast
import os
import sys

from pyjinhx.sfc import split_pjx


def generate_stub(python_src: str) -> str:
    """Return a `.pyi` body: the block source with function bodies replaced by `...`."""
    tree = ast.parse(python_src)

    class _Stripper(ast.NodeTransformer):
        def _strip(self, node):
            self.generic_visit(node)
            doc = ast.get_docstring(node, clean=False)
            body: list[ast.stmt] = []
            if doc is not None:
                body.append(node.body[0])
            body.append(ast.Expr(value=ast.Constant(value=...)))
            node.body = body
            return node

        def visit_FunctionDef(self, node):
            return self._strip(node)

        def visit_AsyncFunctionDef(self, node):
            return self._strip(node)

    stripped = _Stripper().visit(tree)
    ast.fix_missing_locations(stripped)
    return ast.unparse(stripped) + "\n"


def _iter_pjx(root: str) -> "list[str]":
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".pjx" in dirnames:
            dirnames.remove(".pjx")  # never descend into the stub cache
        for name in filenames:
            if name.endswith(".pjx"):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def _stub_path(root: str, pjx_path: str) -> str:
    rel = os.path.relpath(pjx_path, root)
    rel_pyi = os.path.splitext(rel)[0] + ".pyi"
    return os.path.join(root, ".pjx", "stubs", rel_pyi)


def _ensure_gitignore(root: str) -> None:
    cache = os.path.join(root, ".pjx")
    os.makedirs(cache, exist_ok=True)
    gitignore = os.path.join(cache, ".gitignore")
    if not os.path.exists(gitignore):
        with open(gitignore, "w", encoding="utf-8") as handle:
            handle.write("*\n")


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(prog="pyjinhx.stubgen")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--check", action="store_true", help="fail if stubs are stale")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)

    stale: list[str] = []
    for pjx_path in _iter_pjx(root):
        with open(pjx_path, encoding="utf-8") as handle:
            python_src, _ = split_pjx(handle.read())
        if python_src is None:
            continue
        want = generate_stub(python_src)
        out_path = _stub_path(root, pjx_path)
        have = ""
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as handle:
                have = handle.read()
        if args.check:
            if have != want:
                stale.append(os.path.relpath(pjx_path, root))
            continue
        _ensure_gitignore(root)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(want)

    if args.check and stale:
        print("stale stubs:\n  " + "\n  ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
