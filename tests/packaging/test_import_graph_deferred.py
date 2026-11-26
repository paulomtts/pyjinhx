"""Tests for imports allowed only inside function bodies and the render spine's reactive isolation."""

import ast
from pathlib import Path

import pytest

from tests.packaging._import_edges import (
    ALLOWED_INTERNAL_IMPORTS,
    PACKAGE_ROOT,
    internal_imports,
)


def module_level_internal_imports(path: Path) -> set[str]:
    """Every ``pyjinhx.*`` module name imported at module scope by ``path`` —
    i.e. only the file's top-level statements, never descending into a
    function or class body. This is what distinguishes a real module-scope
    edge (which can create an import cycle) from the local-import escape
    hatch base.py uses for pipeline.py/session.py inside render()'s body."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        found.update(n for n in names if n == "pyjinhx" or n.startswith("pyjinhx."))
    return found


RENDER_SPINE_MODULES = (
    "components.base",
    "rendering.pipeline",
    "rendering.root_attrs",
    "rendering.segments",
    "rendering.session",
    "rendering.template_context",
)


def test_component_only_imports_render_and_session_inside_a_method_body():
    """The docstring above and the ALLOWED_INTERNAL_IMPORTS comment on
    "component" both claim pipeline.py/session.py are reached only from inside
    BaseComponent.render()'s method body, never at module scope — because
    pipeline.py imports BaseComponent at import time, so a module-level edge
    back would be a real cycle (#643). Assert that claim directly: the whole
    file's edge table above passes even if the import moves to module scope,
    since it doesn't distinguish where in the file the import lives."""
    module_level = module_level_internal_imports(
        PACKAGE_ROOT / "components" / "base.py"
    )
    assert "pyjinhx.rendering.pipeline" not in module_level
    assert "pyjinhx.rendering.session" not in module_level


def test_importer_only_imports_component_inside_a_function():
    """`import pyjinhx` installs the import hook and must not start importing
    pydantic, which base.py pulls in; the loader reads BaseComponent only
    after a document's block has run."""
    module_level = module_level_internal_imports(
        PACKAGE_ROOT / "components" / "importer.py"
    )
    assert "pyjinhx.components.base" not in module_level


def test_session_only_imports_config_inside_a_function_body():
    """request_scope() reads current_settings() to seed a default session's
    Jinja environment, but config sits above the render spine: a module-scope
    edge would invert the layering and, because config imports the spine at
    import time, would be a genuine cycle. The whole-file edge table can't see
    where in the file an import lives, so pin it here."""
    module_level = module_level_internal_imports(
        PACKAGE_ROOT / "rendering" / "session.py"
    )
    assert "pyjinhx.config" not in module_level


def test_inject_only_imports_config_inside_a_function_body():
    """inject_runtime() reads current_settings() to decide whether to record
    the theme sheet, but config sits above the client tier: a module-scope edge
    would invert the layering and, because config imports the spine at import
    time, would be a genuine cycle. The whole-file edge table can't see where
    in the file an import lives, so pin it here."""
    module_level = module_level_internal_imports(PACKAGE_ROOT / "client" / "inject.py")
    assert "pyjinhx.config" not in module_level


def test_component_only_imports_config_inside_a_function_body():
    """_resolve_tier2() reads current_settings() to find the process's cache
    backend, but config sits above reactive/: a module-scope edge would invert
    the layering and, because config imports the spine at import time, would be
    a genuine cycle. The whole-file edge table can't see where in the file an
    import lives, so pin it here."""
    module_level = module_level_internal_imports(
        PACKAGE_ROOT / "reactive" / "component.py"
    )
    assert "pyjinhx.config" not in module_level


def test_render_cache_only_imports_config_inside_a_function_body():
    """resolve_render_tier2() reads current_settings() to find the process's
    render-cache backend, but config sits above the render spine: a
    module-scope edge would invert the layering and, because config imports
    the spine at import time, would be a genuine cycle. The whole-file edge
    table can't see where in the file an import lives, so pin it here."""
    module_level = module_level_internal_imports(
        PACKAGE_ROOT / "rendering" / "render_cache.py"
    )
    assert "pyjinhx.config" not in module_level


def test_cache_only_imports_config_inside_a_function_body():
    """invalidate() reads current_settings() to sweep the cross-request backend,
    but config sits above reactive/: a module-scope edge would invert the
    layering and, because config imports the spine at import time, would be a
    genuine cycle. The whole-file edge table can't see where in the file an
    import lives, so pin it here."""
    module_level = module_level_internal_imports(PACKAGE_ROOT / "reactive" / "cache.py")
    assert "pyjinhx.config" not in module_level


def test_config_names_the_cache_backend_type_without_importing_it():
    """PjxSettings.cache_backend is annotated CacheBackend | None, but config
    sits above reactive/: a module-scope edge would make importing config pull
    reactive/ in, and config already imports the spine at import time. The
    whole-file edge table can't see where in the file an import lives, so pin
    it here — the import belongs under TYPE_CHECKING and nowhere else."""
    module_level = module_level_internal_imports(PACKAGE_ROOT / "config.py")
    reactive_edges = {
        name for name in module_level if name.startswith("pyjinhx.reactive")
    }
    assert not reactive_edges, (
        f"config.py imports reactive at module scope: {sorted(reactive_edges)}"
    )


def test_props_header_only_imports_component_inside_a_function_body():
    """parse_props_header() resolves the Slot and Children aliases out of
    base.py, but both names are bound at the bottom of that module, after
    _OpenComponent — whose __pydantic_init_subclass__ reenters this module. A
    module-scope import would therefore read them before they exist, deadlocking
    class definition. The whole-file edge table above already permits the
    props_header -> pyjinhx.components.base edge and cannot see where in the file the
    import lives, so pin the scope here."""
    module_level = module_level_internal_imports(
        PACKAGE_ROOT / "components" / "props_header.py"
    )
    assert "pyjinhx.components.base" not in module_level


def test_no_render_spine_module_declares_a_reactive_import():
    """FORBIDDEN per architecture-overview.md: anything in the render spine
    importing reactive/. pyjinhx/reactive/ doesn't exist yet (#288), so this
    guards the allowlist table itself — it must fail the moment someone adds
    a pyjinhx.reactive entry to any spine module's allowed set, before a
    single file under reactive/ is ever written."""
    for module in RENDER_SPINE_MODULES:
        allowed = ALLOWED_INTERNAL_IMPORTS.get(module, frozenset())
        reactive_edges = {
            name
            for name in allowed
            if name == "pyjinhx.reactive" or name.startswith("pyjinhx.reactive.")
        }
        assert not reactive_edges, (
            f"{module} declares forbidden reactive import(s): {sorted(reactive_edges)}"
        )


@pytest.mark.parametrize("stem", RENDER_SPINE_MODULES)
def test_render_spine_modules_do_not_import_reactive_on_disk(stem: str):
    """Redundant with test_no_render_spine_module_declares_a_reactive_import
    while ALLOWED_INTERNAL_IMPORTS is the source of truth, but catches drift
    if a spine file imports pyjinhx.reactive directly without the allowlist
    table being updated to match (e.g. a bypass that skips declaring the
    edge)."""
    path = PACKAGE_ROOT / f"{stem.replace('.', '/')}.py"
    reactive_imports = {
        name
        for name in internal_imports(path)
        if name == "pyjinhx.reactive" or name.startswith("pyjinhx.reactive.")
    }
    assert not reactive_imports, (
        f"{path.name} imports forbidden reactive module(s): {sorted(reactive_imports)}"
    )


def test_document_modules_import_nothing_but_the_scanner():
    """document/ is the static layer manifest and stubgen read without
    importing an application: nothing in it reaches the rest of pyjinhx."""
    for path in sorted((PACKAGE_ROOT / "document").glob("*.py")):
        assert internal_imports(path) <= {"pyjinhx.document.scanner"}, path.name
