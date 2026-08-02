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
    # The TYPE_CHECKING-only RenderSession import mirrors session's own
    # component/segments entries below, for the same reason: the enum/function
    # signature names the type, runtime never touches it.
    # component is a real runtime edge: all_assets() reads
    # BaseComponent.__subclasses__() and each class's descriptor, imported
    # locally to avoid a module-level cycle (session imports assets).
    "assets": frozenset({"pyjinhx2.session", "pyjinhx2.component"}),
    # builtins/ ports v0.x's component library onto the v2 stack, one leaf
    # package per component (#500). Each leaf only reaches down into
    # component.py for BaseComponent/Slot/AttrValue and its own vendored
    # data module; nothing above the leaf imports back.
    "builtins.__init__": frozenset(),
    "builtins.ui.__init__": frozenset(),
    "builtins.ui.pjx_badge.__init__": frozenset(
        {"pyjinhx2.builtins.ui.pjx_badge.pjx_badge"}
    ),
    "builtins.ui.pjx_badge.pjx_badge": frozenset({"pyjinhx2.component"}),
    "builtins.ui.pjx_avatar.__init__": frozenset(
        {"pyjinhx2.builtins.ui.pjx_avatar.pjx_avatar"}
    ),
    "builtins.ui.pjx_avatar.pjx_avatar": frozenset({"pyjinhx2.component"}),
    "builtins.ui.pjx_avatar_stack.__init__": frozenset(
        {"pyjinhx2.builtins.ui.pjx_avatar_stack.pjx_avatar_stack"}
    ),
    "builtins.ui.pjx_avatar_stack.pjx_avatar_stack": frozenset({"pyjinhx2.component"}),
    "builtins.ui.pjx_divider.__init__": frozenset(
        {"pyjinhx2.builtins.ui.pjx_divider.pjx_divider"}
    ),
    "builtins.ui.pjx_divider.pjx_divider": frozenset({"pyjinhx2.component"}),
    "builtins.ui.pjx_icon.__init__": frozenset(
        {"pyjinhx2.builtins.ui.pjx_icon.pjx_icon"}
    ),
    "builtins.ui.pjx_icon._icons": frozenset(),
    "builtins.ui.pjx_icon.pjx_icon": frozenset(
        {"pyjinhx2.component", "pyjinhx2.builtins.ui.pjx_icon._icons"}
    ),
    # The classless factory is a consumer: it validates a tag name, reads the
    # template discovery found, hands the header to props_header and publishes
    # the result through discovery's own write path. Nothing imports it back.
    "classless": frozenset(
        {
            "pyjinhx2",
            "pyjinhx2.component",
            "pyjinhx2.discovery",
            "pyjinhx2.props_header",
            "pyjinhx2.segments",
        }
    ),
    # The client tier is the bottom of the stack: it ships pjx.js and reads it
    # off disk. Nothing in pyjinhx2 may be imported from here, or the browser
    # runtime's delivery would depend on the server tier that serves it.
    "client.__init__": frozenset(),
    # The one sanctioned edge out of the client tier: inject.py writes the
    # runtime payload onto RenderSession and gates on js_mode, mirroring the
    # "dotted edge" architecture-overview.md calls out between L2's
    # RenderSession and L3 (cold render's assets flow through the session).
    "client.inject": frozenset(
        {"pyjinhx2.assets", "pyjinhx2.client", "pyjinhx2.session"}
    ),
    "component": frozenset(
        {"pyjinhx2.descriptor", "pyjinhx2.props_header"}
    ),  # the stale-header probe needs template_has_props_header
    # config sits above everything: it may read the spine to register
    # components and it defers to siblings that own the app wiring and dev
    # tooling. The reverse edge — any spine, reactive/ or client/ module
    # importing config — stays forbidden and is asserted below.
    "config": frozenset(
        {
            "pyjinhx2",
            "pyjinhx2.component",
            "pyjinhx2.discovery",
            "pyjinhx2.dev",
            "pyjinhx2.integrations.fastapi",
        }
    ),
    # context sits above the spine with config and integrations.fastapi: it is a
    # read-only view over session's ContextVars plus the pjx state the FastAPI
    # middleware parsed onto the request. Request is typed from starlette, never
    # imported from integrations.fastapi, so the adapter keeps zero importers
    # below it. Nothing in the spine may import context back.
    "context": frozenset({"pyjinhx2.session"}),
    "descriptor": frozenset(),
    # dev sits above the spine, next to config and context: it walks
    # BaseComponent's subclass tree for the dependency graph and reads the
    # request-scoped dirtied set and cache reverse index for its checks. config
    # imports it (deferred); nothing below may import it back.
    "dev": frozenset({"pyjinhx2.component", "pyjinhx2.session"}),
    # discovery keys the registry by each class's own resolved tag, so it reads
    # component.py's snake-case helper rather than inventing a second naming
    # scheme that could drift from the one templates are probed with.
    "discovery": frozenset({"pyjinhx2.component"}),
    # The framework adapter sits at the very top with config: it orchestrates
    # the request cycle by calling published entry points (request_scope,
    # render, inject_runtime, ReactiveResponse) and nothing imports it back
    # except config's deferred setup() edge.
    "integrations.__init__": frozenset(),
    "integrations.fastapi": frozenset(
        {
            "pyjinhx2.client.inject",
            "pyjinhx2.component",
            "pyjinhx2.config",
            "pyjinhx2.reactive.response",
            "pyjinhx2.render",
            "pyjinhx2.session",
        }
    ),
    "markers": frozenset({"pyjinhx2.component"}),
    # Generating a class from a {#def #} header needs the open-model base to
    # subclass; parsing itself stays pure.
    "props_header": frozenset({"pyjinhx2.component"}),
    # render resolves each ChildRef tag against the published class registry;
    # an unregistered tag is emitted verbatim, so this is a read-only edge.
    "render": frozenset(
        {
            "pyjinhx2.assets",
            "pyjinhx2.component",
            "pyjinhx2.discovery",
            "pyjinhx2.markers",
            "pyjinhx2.props_header",
            "pyjinhx2.render_context",
            "pyjinhx2.segments",
            "pyjinhx2.session",
        }
    ),
    "render_context": frozenset({"pyjinhx2.markers", "pyjinhx2.component"}),
    "reactive.__init__": frozenset(),
    "reactive.keys": frozenset(),
    # cache.py is a store over session's cache ContextVar and nothing else: it
    # owns no state, and it must not reach sideways into keys.py or up into the
    # render spine to key or evict anything.
    "reactive.cache": frozenset({"pyjinhx2.session"}),
    # mutations.py records dirtied keys through session's public writer; it owns
    # no ContextVar of its own and never reaches sideways into cache.py.
    "reactive.mutations": frozenset({"pyjinhx2.session", "pyjinhx2.reactive.keys"}),
    # ReactiveResponse (L3.6.1) composes one body out of the primary render and
    # fanout.py's OOB candidates; it reads the manifest parser, the fanout walk
    # and session's request-scoped dirtied-key/session accessors, and nothing
    # else. No registry edge (ADR 0009): fanout.py already owns registry reads.
    # #489/#488: `candidates()` also evicts the load cache for this request's
    # dirtied keys before walking, so cache.py's `invalidate()` is a direct edge
    # too, not just fanout.py's own transitive one.
    # #490: the asset-delta leg reads assets.py's fragment builder alongside
    # everything the region-swap leg already reads.
    "reactive.response": frozenset(
        {
            "pyjinhx2.client.inject",
            "pyjinhx2.reactive.assets",
            "pyjinhx2.reactive.cache",
            "pyjinhx2.reactive.fanout",
            "pyjinhx2.session",
        }
    ),
    # #490: which of a fan-out's required assets the client is missing, read
    # from the candidates' frozen descriptors (not session accumulation - see
    # the module docstring) and diffed against asset_token()'s identity.
    "reactive.assets": frozenset(
        {
            "pyjinhx2.assets",
            "pyjinhx2.reactive.fanout",
            "pyjinhx2.session",
        }
    ),
    # ReactiveComponent subclasses BaseComponent and routes load() through the
    # cache: the two edges below are the whole design. The reverse - anything in
    # the render spine importing reactive/ - stays forbidden.
    "reactive.component": frozenset(
        {
            "pyjinhx2.component",
            "pyjinhx2.reactive.cache",
            "pyjinhx2.reactive.keys",
        }
    ),
    # The reactive on_rendered branch (#463): it reads ReactiveComponent to
    # decide whether to act and reuses the spine's one splice primitive. Every
    # edge points downward into the spine — root_attrs/segments/session know
    # nothing about this module, and render.py never imports it.
    "reactive.root_attrs": frozenset(
        {
            "pyjinhx2.component",
            "pyjinhx2.reactive.component",
            "pyjinhx2.root_attrs",
            "pyjinhx2.segments",
            "pyjinhx2.session",
        }
    ),
    # The L3.5.1 manifest walk (#466): read-only against discovery (tag ->
    # class), the registry (resolve() only, never register_instance - E7),
    # and the load cache (a separate key space, E13). It re-renders a dirty
    # candidate through render_level(), the same primitive root_attrs.py
    # uses, and falls back to current_session() rather than ever building an
    # unscoped RenderSession with the wrong template_dir. #468 adds the
    # structural nesting dedup pass, which walks segments/ChildRef directly
    # rather than re-parsing or substring-matching rendered markup.
    "reactive.fanout": frozenset(
        {
            "pyjinhx2",
            "pyjinhx2.discovery",
            "pyjinhx2.registry",
            "pyjinhx2.reactive.cache",
            "pyjinhx2.reactive.component",
            "pyjinhx2.reactive.keys",
            "pyjinhx2.render",
            "pyjinhx2.root_attrs",
            "pyjinhx2.segments",
            "pyjinhx2.session",
        }
    ),
    # The instance registry (ADR 0009) is read-only over session's ContextVar
    # store; it consumes get_instances() and nothing else in pyjinhx2. The
    # register_rendered_instance signature also names RenderedLevel, but that
    # import is TYPE_CHECKING-only (see registry.py) — never a runtime edge.
    "registry": frozenset({"pyjinhx2.session", "pyjinhx2.segments"}),
    "root_attrs": frozenset({"pyjinhx2.segments"}),
    "segments": frozenset(),
    # The on_rendered hook's signature names BaseComponent and RenderedLevel, but
    # both imports are TYPE_CHECKING-only. At runtime session also imports
    # AssetMode from assets, a real edge alongside markers.
    "session": frozenset(
        {
            "pyjinhx2.markers",
            "pyjinhx2.component",
            "pyjinhx2.segments",
            "pyjinhx2.assets",
        }
    ),
    # pjx_table family (#526): each component module imports only the core
    # component surface (AttrValue, BaseComponent, Slot); each __init__ just
    # re-exports its class from its co-located module.
    "builtins.pjx_table.__init__": frozenset({"pyjinhx2.builtins.pjx_table.pjx_table"}),
    "builtins.pjx_table.pjx_table": frozenset({"pyjinhx2.component"}),
    "builtins.pjx_table_head.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_table_head.pjx_table_head"}
    ),
    "builtins.pjx_table_head.pjx_table_head": frozenset({"pyjinhx2.component"}),
    "builtins.pjx_table_body.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_table_body.pjx_table_body"}
    ),
    "builtins.pjx_table_body.pjx_table_body": frozenset({"pyjinhx2.component"}),
    "builtins.pjx_table_row.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_table_row.pjx_table_row"}
    ),
    "builtins.pjx_table_row.pjx_table_row": frozenset({"pyjinhx2.component"}),
    "builtins.pjx_table_header_cell.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_table_header_cell.pjx_table_header_cell"}
    ),
    "builtins.pjx_table_header_cell.pjx_table_header_cell": frozenset(
        {"pyjinhx2.component"}
    ),
    "builtins.pjx_table_cell.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_table_cell.pjx_table_cell"}
    ),
    "builtins.pjx_table_cell.pjx_table_cell": frozenset({"pyjinhx2.component"}),
    "builtins.pjx_paginator.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_paginator.pjx_paginator"}
    ),
    "builtins.pjx_paginator.pjx_paginator": frozenset({"pyjinhx2.component"}),
    "builtins.pjx_lazy_load.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_lazy_load.pjx_lazy_load"}
    ),
    "builtins.pjx_lazy_load.pjx_lazy_load": frozenset({"pyjinhx2.component"}),
    "builtins.pjx_region_loader.__init__": frozenset(
        {"pyjinhx2.builtins.pjx_region_loader.pjx_region_loader"}
    ),
    "builtins.pjx_region_loader.pjx_region_loader": frozenset({"pyjinhx2.component"}),
}


def module_paths() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def module_name(path: Path) -> str:
    """Dotted name relative to the package root, e.g. ``reactive.keys``."""
    return ".".join(path.relative_to(PACKAGE_ROOT).with_suffix("").parts)


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
    on_disk = {module_name(path) for path in module_paths()}
    assert on_disk == set(ALLOWED_INTERNAL_IMPORTS)


@pytest.mark.parametrize("path", module_paths(), ids=module_name)
def test_module_imports_only_declared_internal_modules(path: Path):
    allowed = ALLOWED_INTERNAL_IMPORTS[module_name(path)]
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
        module_name(path)
        for path in module_paths()
        if "pyjinhx2.descriptor" in internal_imports(path)
    }
    assert importers == {"component"}


def test_session_never_reaches_into_reactive():
    """session.py owns the per-request ContextVars; reactive/ imports them from
    here. The reverse edge would invert the spine."""
    imports = internal_imports(PACKAGE_ROOT / "session.py")
    assert not any(name.startswith("pyjinhx2.reactive") for name in imports)
    assert imports <= {
        "pyjinhx2.markers",
        "pyjinhx2.component",
        "pyjinhx2.segments",
        "pyjinhx2.assets",
    }


def test_nothing_below_config_imports_config():
    """config is the top of the stack: it reads the spine, reactive/ and
    client/, and none of them may reach back up into it.

    integrations.fastapi is the one declared exception: it sits alongside
    config, not below it, and calls configure_pyjinhx/shutdown_pyjinhx to
    chain the app's lifespan — the two modules' mutual edges are each lazy
    (config imports integrations.fastapi inside setup(), see its own entry
    above) so the runtime cycle never actually executes at import time.
    """
    importers = {
        module_name(path)
        for path in module_paths()
        if "pyjinhx2.config" in internal_imports(path)
    }
    assert importers == {"integrations.fastapi"}


def test_nothing_imports_context():
    """context.py is a leaf consumer. The spine, reactive/ and client/ expose
    state through session.py's accessors; importing the facade back would make
    the view a dependency of the thing it views."""
    importers = {
        module_name(path)
        for path in module_paths()
        if "pyjinhx2.context" in internal_imports(path)
    }
    assert importers == set()


def test_no_render_spine_module_declares_a_reactive_import():
    """FORBIDDEN per architecture-overview.md: anything in the render spine
    importing reactive/. pyjinhx2/reactive/ doesn't exist yet (#288), so this
    guards the allowlist table itself — it must fail the moment someone adds
    a pyjinhx2.reactive entry to any spine module's allowed set, before a
    single file under reactive/ is ever written."""
    for module in RENDER_SPINE_MODULES:
        allowed = ALLOWED_INTERNAL_IMPORTS.get(module, frozenset())
        reactive_edges = {
            name
            for name in allowed
            if name == "pyjinhx2.reactive" or name.startswith("pyjinhx2.reactive.")
        }
        assert not reactive_edges, (
            f"{module} declares forbidden reactive import(s): {sorted(reactive_edges)}"
        )


RENDER_SPINE_MODULES = (
    "component",
    "descriptor",
    "markers",
    "render",
    "render_context",
    "root_attrs",
    "segments",
    "session",
)


@pytest.mark.parametrize("stem", RENDER_SPINE_MODULES)
def test_render_spine_modules_do_not_import_reactive_on_disk(stem: str):
    """Redundant with test_no_render_spine_module_declares_a_reactive_import
    while ALLOWED_INTERNAL_IMPORTS is the source of truth, but catches drift
    if a spine file imports pyjinhx2.reactive directly without the allowlist
    table being updated to match (e.g. a bypass that skips declaring the
    edge)."""
    path = PACKAGE_ROOT / f"{stem}.py"
    reactive_imports = {
        name
        for name in internal_imports(path)
        if name == "pyjinhx2.reactive" or name.startswith("pyjinhx2.reactive.")
    }
    assert not reactive_imports, (
        f"{path.name} imports forbidden reactive module(s): {sorted(reactive_imports)}"
    )
