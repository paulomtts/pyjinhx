"""Generate signature-only `.pyi` stubs for `.pjx` single-file components.

Stubs let a type checker resolve component imports — both from ordinary `.py`
files and, crucially, between `.pjx` components in the same package. They are
written **next to** each `.pjx` (e.g. ``counter.pyi`` beside ``counter.pjx``)
because a type checker anchors a regular package to its source directory and
will not fall back to a separate stub tree for a `.pjx`-only submodule. The
generated files are gitignored (a managed block in the repo-root ``.gitignore``)
and never hand-edited.
"""
import argparse
import ast
import os
import sys

from pyjinhx.sfc import split_pjx

_GITIGNORE_BEGIN = "# >>> pyjinhx generated stubs (do not edit) >>>"
_GITIGNORE_END = "# <<< pyjinhx generated stubs <<<"


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
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".pjx"):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def _stub_path(pjx_path: str) -> str:
    """The stub sits next to the `.pjx` so the type checker resolves it as a
    submodule of the same package (e.g. ``counter.pjx`` → ``counter.pyi``)."""
    return os.path.splitext(pjx_path)[0] + ".pyi"


def _update_gitignore(root: str, stub_paths: "list[str]") -> None:
    """Rewrite the managed pyjinhx-stubs block in ``<root>/.gitignore`` to list
    every generated stub (repo-relative, forward slashes). Leaves the rest of
    the file untouched."""
    gitignore = os.path.join(root, ".gitignore")
    lines: list[str] = []
    if os.path.exists(gitignore):
        with open(gitignore, encoding="utf-8") as handle:
            lines = handle.read().splitlines()

    # Drop any previous managed block.
    cleaned: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == _GITIGNORE_BEGIN:
            skipping = True
            continue
        if line.strip() == _GITIGNORE_END:
            skipping = False
            continue
        if not skipping:
            cleaned.append(line)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()

    block = [_GITIGNORE_BEGIN]
    block += [os.path.relpath(p, root).replace(os.sep, "/") for p in stub_paths]
    block.append(_GITIGNORE_END)

    out = (cleaned + [""] if cleaned else []) + block
    with open(gitignore, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(prog="pyjinhx.stubgen")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--check", action="store_true", help="fail if stubs are stale")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)

    stale: list[str] = []
    written: list[str] = []
    for pjx_path in _iter_pjx(root):
        with open(pjx_path, encoding="utf-8") as handle:
            python_src, _ = split_pjx(handle.read())
        if python_src is None:
            continue
        want = generate_stub(python_src)
        out_path = _stub_path(pjx_path)
        have = ""
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as handle:
                have = handle.read()
        if args.check:
            if have != want:
                stale.append(os.path.relpath(pjx_path, root))
            continue
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(want)
        written.append(out_path)

    if args.check and stale:
        print("stale stubs:\n  " + "\n  ".join(stale), file=sys.stderr)
        return 1
    if not args.check:
        _update_gitignore(root, written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
