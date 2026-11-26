"""Tests for the declared internal import edge table and the hub-module import rules.

document/ imports nothing else in pyjinhx. components/base.py (the component
class and its ClassDescriptor) must never reach up into rendering/ for anything
at module scope: its render() method imports rendering/pipeline.py and
rendering/session.py from inside the method body, since pipeline.py imports
BaseComponent at import time and a module-level edge back would be a real cycle
(#643). components/base.py's ClassDescriptor is built and attached in
__pydantic_init_subclass__ (#271) and nothing else imports it. rendering/segments.py
is import-pure — stdlib only (also asserted in test_segments.py); the edge
table in _import_edges.py is the whole-package view, so a new module cannot
quietly add an edge nobody declared.
"""

import ast
from pathlib import Path

import pytest

from tests.packaging._import_edges import (
    ALLOWED_INTERNAL_IMPORTS,
    PACKAGE_ROOT,
    internal_imports,
)


def module_paths() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def module_name(path: Path) -> str:
    """Dotted name relative to the package root, e.g. ``reactive.keys``."""
    return ".".join(path.relative_to(PACKAGE_ROOT).with_suffix("").parts)


def test_every_module_is_covered_by_the_declared_edge_table():
    """A new module must declare its edges in `_import_edges.py` before it can be
    imported anywhere — otherwise the table silently stops being a whole-package
    view."""
    on_disk = {module_name(path) for path in module_paths()}
    assert on_disk == set(ALLOWED_INTERNAL_IMPORTS)


@pytest.mark.parametrize("path", module_paths(), ids=module_name)
def test_module_imports_only_declared_internal_modules(path: Path):
    allowed = ALLOWED_INTERNAL_IMPORTS[module_name(path)]
    unexpected = internal_imports(path) - allowed
    assert not unexpected, (
        f"{path.name} imports undeclared internal modules: {sorted(unexpected)}"
    )


def test_segments_imports_nothing_from_pyjinhx():
    assert internal_imports(PACKAGE_ROOT / "rendering" / "segments.py") == set()


def test_component_is_the_only_importer_of_class_descriptor():
    """ClassDescriptor is defined in components/base.py and nothing imports it:
    anything else naming it means the fact sheet is being rebuilt somewhere it
    should be read from the class instead."""
    importers = set()
    for path in module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name == "ClassDescriptor" for alias in node.names
            ):
                importers.add(module_name(path))
    assert importers == set()


def test_session_never_reaches_into_reactive():
    """session.py owns the per-request ContextVars; reactive/ imports them from
    here. The reverse edge would invert the spine."""
    imports = internal_imports(PACKAGE_ROOT / "rendering" / "session.py")
    assert not any(name.startswith("pyjinhx.reactive") for name in imports)
    assert imports <= {
        "pyjinhx.rendering.template_context",
        "pyjinhx.components.base",
        "pyjinhx.rendering.segments",
        "pyjinhx.rendering.assets",
        "pyjinhx.config",
        "pyjinhx.components.importer",
        "pyjinhx.document.scanner",
        "pyjinhx.document.template_blocks",
    }


def test_nothing_below_config_imports_config():
    """config is the top of the stack: it reads the spine, reactive/ and
    client/, and none of them may reach back up into it.

    integrations.fastapi is the one declared exception: it sits alongside
    config, not below it, and calls configure_pyjinhx/shutdown_pyjinhx to
    chain the app's lifespan — the two modules' mutual edges are each lazy
    (config imports integrations.fastapi inside setup(), see its own entry
    above) so the runtime cycle never actually executes at import time.

    session.py is the second exception, and a lazy one: request_scope() calls
    current_settings() inside its own body to seed a default session's Jinja
    environment. The edge never executes at import time, and
    test_session_only_imports_config_inside_a_function_body pins it there.

    reactive/component.py and reactive/cache.py are the third and fourth, and
    lazy in the same way: _resolve_tier2() and invalidate() call
    current_settings() inside their own bodies to find the process's cache
    backend. test_component_only_imports_config_inside_a_function_body and
    test_cache_only_imports_config_inside_a_function_body pin them there.

    render_cache.py is the fifth, and lazy for the same reason:
    resolve_render_tier2() calls current_settings() inside its own body to find
    the process's render-cache backend. config sits above the render spine, so
    a module-scope edge would be a genuine cycle.
    test_render_cache_only_imports_config_inside_a_function_body pins it there.

    client/inject.py is the sixth, lazy for the same reason: inject_runtime()
    calls current_settings() inside its own body to decide whether to record
    the theme sheet. test_inject_only_imports_config_inside_a_function_body
    pins it there.
    """
    importers = {
        module_name(path)
        for path in module_paths()
        if "pyjinhx.config" in internal_imports(path)
    }
    assert importers == {
        "client.inject",
        "integrations.fastapi",
        "reactive.cache",
        "reactive.component",
        "rendering.render_cache",
        "rendering.session",
    }


def test_nothing_imports_context():
    """context.py is a leaf consumer. The spine, reactive/ and client/ expose
    state through session.py's accessors; importing the facade back would make
    the view a dependency of the thing it views."""
    importers = {
        module_name(path)
        for path in module_paths()
        if "pyjinhx.context" in internal_imports(path)
    }
    assert importers == set()
