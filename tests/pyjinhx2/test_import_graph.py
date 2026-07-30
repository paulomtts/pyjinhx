"""The declared import direction for pyjinhx2, enforced statically.

component.py sits below descriptor.py and render.py and must never reach up into
them for anything but the one sanctioned edge: the ClassDescriptor it builds and
attaches in __pydantic_init_subclass__ (#271). descriptor.py and segments.py are
import-pure — stdlib only. Per-module purity is also asserted in
test_descriptor.py and test_segments.py; this file is the whole-package view, so
a new module cannot quietly add an edge nobody declared.
"""

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "pyjinhx2"

# Every internal edge pyjinhx2 is allowed to have, module -> modules it may
# import. A module absent from a value list may not be imported by that key.
# Add an entry here deliberately when a new edge is designed, never to make a
# failing test go green.
ALLOWED_INTERNAL_IMPORTS: dict[str, frozenset[str]] = {
    "__init__": frozenset(),
    "component": frozenset({"pyjinhx2.descriptor"}),
    "descriptor": frozenset(),
    "markers": frozenset({"pyjinhx2.component"}),
    "render_context": frozenset({"pyjinhx2.markers", "pyjinhx2.component"}),
    "segments": frozenset(),
}


def module_paths() -> list[Path]:
    return sorted(PACKAGE_ROOT.glob("*.py"))


def internal_imports(path: Path) -> set[str]:
    """Every ``pyjinhx2.*`` module name imported by ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, (
                f"{path.name} must use absolute imports, not relative ones"
            )
            names = [node.module or ""]
        else:
            continue
        found.update(n for n in names if n == "pyjinhx2" or n.startswith("pyjinhx2."))
    return found


def test_every_module_is_covered_by_the_declared_edge_table():
    """A new module must declare its edges here before it can be imported
    anywhere — otherwise the table silently stops being a whole-package view."""
    on_disk = {path.stem for path in module_paths()}
    assert on_disk == set(ALLOWED_INTERNAL_IMPORTS)


@pytest.mark.parametrize("path", module_paths(), ids=lambda p: p.stem)
def test_module_imports_only_declared_internal_modules(path: Path):
    allowed = ALLOWED_INTERNAL_IMPORTS[path.stem]
    unexpected = internal_imports(path) - allowed
    assert not unexpected, (
        f"{path.name} imports undeclared internal modules: {sorted(unexpected)}"
    )


def test_descriptor_imports_nothing_from_pyjinhx2():
    assert internal_imports(PACKAGE_ROOT / "descriptor.py") == set()


def test_segments_imports_nothing_from_pyjinhx2():
    assert internal_imports(PACKAGE_ROOT / "segments.py") == set()


def test_component_is_the_only_importer_of_class_descriptor():
    """The wiring seam (#271) is the one sanctioned reach upward. Anything else
    importing ClassDescriptor means the fact sheet is being rebuilt somewhere it
    should be read from the class instead."""
    importers = {
        path.stem
        for path in module_paths()
        if "pyjinhx2.descriptor" in internal_imports(path)
    }
    assert importers == {"component"}
