# Package layout: role-based subpackages — implementation plan

Branch: **`refactor/package-layout`**, worktree `.claude/worktrees/pkg-layout`.
Written against master `ed7e97b5` (pyjinhx 1.17.0). Planning only: this document
moves no code.

Implement **after** these three have merged to master, then rebase onto it:

| branch | what it changes for this plan |
|---|---|
| `refactor/flatten-builtins` | `pyjinhx/builtins/ui/*` becomes `pyjinhx/builtins/*`; rewrites the builtins half of `ALLOWED_INTERNAL_IMPORTS`. Every builtin still imports `pyjinhx._component` (76 modules today), which this plan renames. |
| `refactor/examples-sfc` | `examples/todo` becomes `{#python` documents. One deep import survives: `examples/todo/components/app/__init__.py:9`. |
| `refactor/tests-layout` | `tests/pyjinhx/*` becomes `tests/unit/*` and friends. Its plan file did not exist when this was written (the branch had no commits), so section 9 states the mapping as a rule plus a table by module. |

Line numbers below are master `ed7e97b5`. The core modules are not touched by the
three branches, so `pyjinhx/*.py` line numbers hold; anything under `tests/`,
`pyjinhx/builtins/` or `examples/` must be re-located with the grep given beside
it.

## Ground rules

- No behaviour change. `from pyjinhx import …` and `from pyjinhx.builtins import …`
  resolve to the same objects. Deep import paths break cleanly, with no shims.
- `python -m pyjinhx.manifest` and `python -m pyjinhx.stubgen` keep working
  (pjx-ls runs the first).
- Absolute imports only (`test_import_graph.py` asserts `node.level == 0`).
- The three new `__init__.py` files are **empty** and stay empty. `import pyjinhx`
  runs two of them; a re-export there would pull pydantic and jinja2 into a bare
  import.
- Gate, from the worktree root, with the worktree's own environment (`uv run`,
  never another checkout's interpreter: several tests start a subprocess that
  imports the *installed* pyjinhx): `uv run ruff format --check .` ·
  `uv run ruff check .` · `uv run pytest -q` · `uvx "basedpyright==1.39.9" pyjinhx/`
  · `uv run mkdocs build --strict` with `docs/superpowers` moved out for the
  duration and moved back (move, never delete).
- Never `git stash`, never `git reset --hard`, do not push. Files under
  `docs/superpowers/` need `git add -f`.

## 1. Decisions

The approved sketch was evaluated module by module against the import graph and
the layering tests. Where the evidence disagreed with the sketch, the plan
follows the evidence; each such row can be reverted on its own (section 12 gives
the cost).

| sketch | plan | why |
|---|---|---|
| `document/`: sfc, template_blocks, props_header, segments, root_attrs, markers | `document/`: **scanner** (was sfc), **template_blocks** only | `segments`, `root_attrs` and `markers` do not parse `.pjx` documents. `segments` is the model of *rendered output* (`RenderedLevel`, `ChildRef`, `VerbatimParser`, `splice`, `serialize`), `root_attrs` stamps attributes onto a `RenderedLevel`, `markers` holds the opaque slot nodes of a template context and imports `BaseComponent` at module scope. They go to `rendering/`. `props_header` imports pydantic, resolves annotations with `pkgutil.resolve_name` and builds component classes (function-local `_component` imports); it goes to `components/`. What is left has **no outgoing internal edge at all**, which is the rule that makes `document/` worth having: it is the static layer `manifest` and `stubgen` read without importing an application. |
| `components/`: _component (+descriptor), classless, registry, discovery, importer | `components/`: **base** (was `_component`, + descriptor), classless, discovery, importer, props_header | `registry.py` is the *request-scoped instance* registry; it imports only `session` and is read by `reactive.fanout` and `integrations.fastapi`. The tag -> class registry lives in `discovery.py`. Inside `components/` a file called `registry.py` would be read as the class registry. It goes to `rendering/`, beside the `session` that owns its ContextVar, and keeps its name (the docs call it "the instance registry" throughout). |
| `rendering/`: rendering, session, render_cache, assets, responses, context (three merged) | `rendering/`: **pipeline** (was rendering), session, render_cache, assets, segments, root_attrs, registry, **template_context** (markers + render_context) | See the next three rows. |
| merge `context` + `app_context` + `render_context` | **not merged as three.** `render_context` merges with `markers`; `context.py` and `app_context.py` stay as they are, top level | Three tests say these sit in three different layers. `app_context` is stdlib-only and imported by `reactive.component` at module scope (`test_import_graph.py:41`). `context` (PjxContext) is the wiring layer: `test_nothing_imports_context` (`test_import_graph.py:938`) and `test_lower_layers_do_not_import_the_wiring_layer` (`tests/pyjinhx/integrations/test_reactive_request_cycle.py:507`, `upper` at :529) forbid `reactive/` and the spine from importing it. `render_context` is a spine module with one importer (`rendering.py:32`). One merged file would be imported by `reactive.component` *and* by the render pipeline, so all three rules would have to be deleted. The three share a word, not a job. The cohesive merge is `render_context` (124 lines, only ever used with `markers`) into `markers`: both are "what a template sees". |
| `responses` in `rendering/` | `integrations/responses.py` | It imports `reactive.assets`, `reactive.cache` and `reactive.fanout`, so it sits *above* `reactive/`; its only importer is `integrations.fastapi` (`fastapi.py:35`) and its own docstring says "every backend funnels its handler returns through this module". In `rendering/` it would be the one module there that imports the fan-out. |
| `tools/`: manifest, stubgen, dev (+ two top-level forwarders) | **no `tools/`.** `manifest.py`, `stubgen.py`, `dev.py` stay top level | `manifest` and `stubgen` *are* the documented entry points; moving them costs two extra forwarding files and buys nothing (5 files instead of 3). `dev.py` is not a tool: it is runtime reactive diagnostics that `config` toggles (`config.py:150`, `from pyjinhx import dev`), and the layering test lists `pyjinhx.dev` in the wiring layer with `config` and `context`. `block_grammar.json` must also stay at `pyjinhx/block_grammar.json`: pjx-ls's `scripts/sync-pyjinhx.mjs:39` reads that path from a checkout, and its CI fails on drift. |
| `sfc.py` -> `document/scanner.py`, maybe split | one module, `document/scanner.py` | Seven concerns, 603 lines, all stdlib-only static reading of a document: comment lexer, block keywords and error codes, `{#python` block, inline `template` extraction, header signature, module naming, the PascalCase/snake naming rules. Every one has two or more consumers among `importer`, `base`, `discovery`, `props_header`, `manifest`, `stubgen`. A split gives three files of 50 to 130 lines and more imports on the `import pyjinhx` path (`importer` needs the block, the naming *and* the module-name parts). The name `sfc` is stale (the docstring still opens with single-file components); `scanner` is not. The module docstring's first paragraph is rewritten to say what it holds. |
| `_component.py` | `components/base.py` | `pyjinhx.components._component` stutters; the docstring calls it "the component base class". The rename costs nothing extra, every importer changes anyway. |
| `rendering.py` | `rendering/pipeline.py`, **not** `rendering/render.py` | With `render.py`, a stale `from pyjinhx.rendering import render` would *succeed* and bind the submodule, failing later with "'module' object is not callable". With `pipeline.py` it is an `ImportError` at the import line, which is the clean break asked for. |

What stays at top level, and why that is a rule and not a leftover: the top level
is **the wiring layer and the command line** — exactly the set the layering test
calls `upper` (`config`, `context`, `dev`, `integrations/`) plus `app_context`
(a stdlib-only public marker class) and the two `python -m` modules with their
grammar data.

Module count: 23 flat modules become 21 (two merges) in three new packages plus
one file added to `integrations/`.

## 2. Final tree

```
pyjinhx/
  __init__.py            public API, lazy; installs the .pjx import hook
  __init__.pyi           public API for type-checkers
  py.typed
  config.py              PjxSettings, setup(), configure/shutdown
  context.py             PjxContext: read-only request handle (wiring layer)
  app_context.py         AppContext marker + load() context-parameter lookup (stdlib-only)
  dev.py                 reactive dev diagnostics: dependency graph, unconsumed-mutation check
  manifest.py            python -m pyjinhx.manifest: components as JSON, without importing them
  stubgen.py             python -m pyjinhx.stubgen: .pyi beside each {#python document
  block_grammar.json     the block grammar as data (path read by pjx-ls)
  block_grammar.README.md
  document/              static reading of a pjx document; imports nothing else in pyjinhx
    __init__.py          empty
    scanner.py           comment lexer, {#python block, inline-template extraction, header
                         signature, module naming, naming rules (stdlib-only)
    template_blocks.py   {#def/{#css/{#js blocks: find, hide, inline assets (jinja2)
  components/            what a component class is and how one comes to exist
    __init__.py          empty
    base.py              BaseComponent, Slot, Children, ClassDescriptor and its resolution
    classless.py         component(): a class for a template nobody declared
    discovery.py         the .pjx walk and the tag -> class registry
    importer.py          the meta-path finder/loader that imports a {#python document
    props_header.py      {#def#} header -> prop spec -> component class
  rendering/             one request's render: session, pipeline, output model
    __init__.py          empty
    pipeline.py          render_level() and the public render()
    session.py           RenderSession, the Jinja environment/loader, request_scope, ContextVars
    template_context.py  the Jinja context of a component: build_context, ComponentNode, SlotProps, slot tokens
    segments.py          RenderedLevel, ChildRef, VerbatimParser, splice, serialize (stdlib-only)
    root_attrs.py        stamp pass-through attrs on a level's root tag (stdlib-only)
    assets.py            AssetMode, emission, manifest, hashing
    render_cache.py      tier-2 render cache: key, store, restore
    registry.py          request-scoped instance registry
  integrations/
    base.py fastapi.py diskcache.py   (unchanged)
    responses.py         compose(): what one handler return becomes (moved in)
  reactive/ builtins/ client/         (unchanged)
```

## 3. Old -> new

| old | new | change |
|---|---|---|
| `pyjinhx/sfc.py` | `pyjinhx/document/scanner.py` | move + rename |
| `pyjinhx/template_blocks.py` | `pyjinhx/document/template_blocks.py` | move |
| `pyjinhx/_component.py` | `pyjinhx/components/base.py` | move + rename |
| `pyjinhx/descriptor.py` | folded into `pyjinhx/components/base.py` | merge |
| `pyjinhx/classless.py` | `pyjinhx/components/classless.py` | move |
| `pyjinhx/discovery.py` | `pyjinhx/components/discovery.py` | move |
| `pyjinhx/importer.py` | `pyjinhx/components/importer.py` | move |
| `pyjinhx/props_header.py` | `pyjinhx/components/props_header.py` | move |
| `pyjinhx/rendering.py` | `pyjinhx/rendering/pipeline.py` | move + rename |
| `pyjinhx/session.py` | `pyjinhx/rendering/session.py` | move |
| `pyjinhx/render_cache.py` | `pyjinhx/rendering/render_cache.py` | move |
| `pyjinhx/assets.py` | `pyjinhx/rendering/assets.py` | move, **one code line changes** (section 6) |
| `pyjinhx/segments.py` | `pyjinhx/rendering/segments.py` | move |
| `pyjinhx/root_attrs.py` | `pyjinhx/rendering/root_attrs.py` | move |
| `pyjinhx/registry.py` | `pyjinhx/rendering/registry.py` | move |
| `pyjinhx/markers.py` | `pyjinhx/rendering/template_context.py` | move + rename |
| `pyjinhx/render_context.py` | folded into `pyjinhx/rendering/template_context.py` | merge |
| `pyjinhx/responses.py` | `pyjinhx/integrations/responses.py` | move |
| `config.py`, `context.py`, `app_context.py`, `dev.py`, `manifest.py`, `stubgen.py`, `__init__.py`, `__init__.pyi`, `py.typed`, `block_grammar.json`, `block_grammar.README.md`, `reactive/`, `integrations/*`, `builtins/`, `client/` | same | none |

Dotted names follow the same table (`pyjinhx.session` -> `pyjinhx.rendering.session`).

## 4. Merges

### 4.1 `descriptor.py` into `components/base.py`

- Move the `ClassDescriptor` dataclass (`descriptor.py:13-39`) verbatim to
  directly below `logger = logging.getLogger("pyjinhx")` (`_component.py:51`),
  above `_auto_id_counter`.
- Delete `from pyjinhx.descriptor import ClassDescriptor` (`_component.py:34`);
  add `from dataclasses import dataclass` after `from collections.abc import Mapping`
  (`Mapping` and `Path` are already imported).
- Module docstring (`_component.py:1-11`): drop "Imports pydantic and
  ClassDescriptor from descriptor.py at module scope"; the rest stands with the
  new file names.
- Resulting top-level order: imports, `logger`, `ClassDescriptor`, then the file
  exactly as today (`_auto_id` ... `BaseComponent` ... `Slot`, `Children`,
  `all_component_classes`, `_is_live`).
- Lost with the file: "descriptor.py is import-pure". Kept in a new form: nothing
  else in `pyjinhx/` imports `ClassDescriptor` (section 7.3).

### 4.2 `render_context.py` into `rendering/template_context.py`

- The file is `markers.py` followed by the body of `render_context.py` from
  `_slot_item_html` (`render_context.py:14`) to the end.
- Imports: `markers.py`'s, plus `from typing import Any` and
  `from markupsafe import Markup`. `from pyjinhx.markers import ComponentNode,
  finalize_slot_node` (`render_context.py:11`) disappears.
- Docstring: "The Jinja context a component's template renders with, and the
  opaque slot nodes inside it."
- Resulting top-level order: `SlotProps`, `ComponentNode`, `SLOT_TOKEN_RE`,
  `_slot_tokens`, `slot_token_table`, `collect_slot_tokens`, `finalize_slot_node`,
  `_slot_item_html`, `_SlotList`, `_SlotDict`, `_wrap_slot_value`, `build_context`.
- New effective edge: `session` imports `finalize_slot_node` from this module, so
  it now also loads `build_context`. Same imports as before (`components.base`,
  markupsafe); nothing new is loaded.

## 5. Public API, lazy maps, CLI modules

`pyjinhx/__init__.py`:

| line | old | new |
|---|---|---|
| 4-5 (docstring) | `pyjinhx.registry`, `pyjinhx.rendering` | `pyjinhx.rendering.registry`, `pyjinhx.rendering.pipeline` |
| 14 | `import pyjinhx.importer as _importer` | `import pyjinhx.components.importer as _importer` |
| 43-45 | `"pyjinhx._component"` (BaseComponent, Children, Slot) | `"pyjinhx.components.base"` |
| 46 | `"pyjinhx.classless"` | `"pyjinhx.components.classless"` |
| 48 | `"pyjinhx.rendering"` | `"pyjinhx.rendering.pipeline"` |
| 49 | `"pyjinhx.session"` | `"pyjinhx.rendering.session"` |
| 59 | `"pyjinhx.assets"` | `"pyjinhx.rendering.assets"` |
| 50-58 | config, context, app_context, reactive.* | unchanged |

`pyjinhx/__init__.pyi`: lines 3, 4, 5 (`_component`), 7 (`assets`), 8
(`classless`), 18 (`rendering`), 19 (`session`) take the same new paths; `__all__`
is unchanged. `pyjinhx/builtins/__init__.py` and `.pyi` name only
`pyjinhx.builtins.*` and are not touched.

**CLI forwarding modules: none are needed.** `pyjinhx/manifest.py` and
`pyjinhx/stubgen.py` do not move, so `python -m pyjinhx.manifest [--grammar]`,
`python -m pyjinhx.stubgen`, `from pyjinhx import manifest`, the stub marker
`# pyjinhx.stubgen: generated from …` and `tests/test_package_layout.py:55-62`
all hold as they are. Their only edits are three import lines each way:
`manifest.py:55` (`pyjinhx.sfc`), `:131` and `:384` (`pyjinhx.template_blocks`,
both function-local, which is what keeps a bare `import pyjinhx.manifest`
stdlib-only), and `stubgen.py:31` with its docstring at `:8`.

If the maintainer wants `tools/` after all (section 12, Q2), the forwarder is
this, for each of the two:

```python
"""``python -m pyjinhx.manifest``; the code lives in ``pyjinhx.tools.manifest``."""

from pyjinhx.tools.manifest import *  # noqa: F403
from pyjinhx.tools.manifest import main

if __name__ == "__main__":
    raise SystemExit(main())
```

with `__all__` added to the real modules so the star import is exact,
`resources.files("pyjinhx")` in `grammar_text` left alone (the JSON does not
move), `prog="python -m pyjinhx.manifest"` left alone, and `_MARKER_PREFIX` in
stubgen left spelling `pyjinhx.stubgen`.

## 6. Package data, build, and strings that name modules

- **Build**: `[tool.hatch.build.targets.wheel] packages = ["pyjinhx"]` ships
  everything under `pyjinhx/`; no config change. Prototype wheels: 378 files
  before, 379 after, 181 non-`.py` files in both, `block_grammar.json`,
  `block_grammar.README.md`, `py.typed` and both `.pyi` present in both.
- **`block_grammar.json` / `.README.md`**: stay. `manifest.py:1127` reads it with
  `resources.files("pyjinhx")`, `tests/pyjinhx/test_manifest.py:14` likewise,
  pjx-ls by path. `block_grammar.README.md:18` names `pyjinhx/manifest.py`, still
  true.
- **Client and builtin assets**: `client/__init__.py:7-56` and each builtin
  resolve beside their own file; nothing moves.
- **`assets.py:30` — the one line of code that must change by hand**:
  `_BUILTIN_ASSET_DIR = Path(__file__).resolve().parent / "builtins"` becomes
  `.parent.parent / "builtins"`. Left alone it points at
  `pyjinhx/rendering/builtins`, `_is_builtin_asset` answers False for every
  builtin and the builtin-before-app CSS ordering (ADR 0003) silently stops.
  `test_is_builtin_asset_true_for_a_path_under_pyjinhx_builtins`
  (`tests/pyjinhx/test_assets.py:284`) fails if it is forgotten (confirmed in the
  prototype). No other moved module anchors a path on its own `__file__`.
- **Lazy maps**: section 5. `config.py:271` walks `pyjinhx.builtins._lazy_imports`,
  unchanged.
- **`from pyjinhx import <submodule>`** in source: `classless.py:22`
  (`discovery`), `reactive/fanout.py:37` (`discovery, registry`) become
  `from pyjinhx.components import discovery` and `from pyjinhx.rendering import
  registry`. `config.py:150` (`from pyjinhx import dev`) is unchanged, and so are
  the `sys.modules["pyjinhx.dev"]` tricks in `tests/pyjinhx/test_config_v2.py:177,191`.
- **`importlib.import_module` / `pkgutil.resolve_name`**: `importer.py:122` and
  `props_header.py:89` resolve *application* names; neither holds a pyjinhx path.
- **`__module__` of generated classes**: `props_header.py:248` passes
  `__module__=__name__`, which becomes `pyjinhx.components.props_header`;
  `classless.py:276` then overwrites it with the synthetic `pyjinhx._classless_N`
  (`classless.py:88`, a literal, unchanged).
  `tests/pyjinhx/test_classless_factory.py:204` asserts the class does not keep
  the props_header name; the codemod updates the string to the new name so the
  assertion keeps its meaning.
- **Cache keys** (`render_cache.py:152,237`, `reactive/component.py:643`,
  `reactive/load_cost.py:80`, `discovery.py:96`): built from the *component
  class's* `__module__.__qualname__`. No renderable class is defined in a moved
  module, so no key changes here (builtin keys change with flatten-builtins,
  not with this).
- **Pickled cache values**: a persistent backend (diskcache) written by <= 1.17
  holds render-cache entries pickled as `pyjinhx.segments.RenderedLevel` /
  `ChildRef`. After the move unpickling raises `ModuleNotFoundError`;
  `load_rendered_level` (`render_cache.py:380`) treats any backend exception as a
  miss, `note_failure` logs one warning per backend, and the next store overwrites
  the entry. So: one warning, misses until rewritten, no error. The render-cache
  key has no schema version to bump, and adding one is a behaviour change, so the
  plan only documents it (CHANGELOG: "clear a persistent cache directory when
  upgrading").
- **Loggers**: every moved module uses the literal `"pyjinhx"`; names do not shift.
- **`_pascal_to_snake`** (`_component.py:224`, alias of `sfc.pascal_to_snake`):
  moves with `base.py`. Importers: `discovery.py:17`, `reactive/root_attrs.py`,
  `docs/hooks.py:13`, `scripts/bench_mixed_reactive_tree.py:33`,
  `bench_render_depth.py:30`, `bench_slot_payload.py:43`, and tests. Not removed
  here.

## 7. Import graph

### 7.1 Package-level edges after the move (computed from the prototype)

```
document    -> (nothing)
components  -> document
            -> rendering   base -> pipeline, session: inside BaseComponent.render() only
                           classless -> segments: one regex constant
            -> client      base -> client.inject: function-local
rendering   -> document, components
            -> reactive    render_cache -> backend, backend_health (protocol and health state)
            -> config      session, render_cache: function-local
reactive    -> components, rendering, app_context; config function-local
integrations-> components, rendering, reactive, client, config
client      -> rendering (assets, session); config function-local
config      -> components, integrations.base; builtins, dev, integrations.fastapi function-local
context     -> rendering.session        dev -> components.base, rendering.session
manifest    -> document, stubgen        stubgen -> document
__init__    -> components.importer
```

No module-level cycle exists: every module was imported first in a fresh
interpreter in the prototype. The function-local imports that prevent cycles
today (`_component.py:496,553,739,740,741,907`, `importer.py:152,224`,
`props_header.py:185,229`, `assets.py:346`, and the `current_settings()` reads
at `session.py:508` and `render_cache.py:259`) stay function-local; the move must not hoist any of
them.

`import pyjinhx` loads `pyjinhx`, `pyjinhx.components`, `pyjinhx.components.importer`,
`pyjinhx.document`, `pyjinhx.document.scanner`: two empty package modules more
than today, no pydantic, no jinja2. Measured with `-X importtime`: 12.3-12.7 ms
before, 12.4-13.0 ms after (noise).

### 7.2 `ALLOWED_INTERNAL_IMPORTS` (`tests/pyjinhx/test_import_graph.py:25`)

Keys are paths relative to the package, so every moved module's key changes; the
codemod rewrites the *values* (they are `"pyjinhx.x"` strings), the keys are a
hand edit:

| old key | new key |
|---|---|
| `sfc` | `document.scanner` |
| `template_blocks` | `document.template_blocks` |
| `_component` + `descriptor` | `components.base` (the `_component` set, minus the self-edge the codemod leaves where `pyjinhx.descriptor` was) |
| `classless`, `discovery`, `importer`, `props_header` | `components.<same>` |
| `rendering` | `rendering.pipeline` |
| `session`, `render_cache`, `assets`, `segments`, `root_attrs`, `registry` | `rendering.<same>` |
| `markers` + `render_context` | `rendering.template_context` = `{"pyjinhx.components.base"}` |
| `responses` | `integrations.responses` |
| (new) | `document.__init__`, `components.__init__`, `rendering.__init__` = `frozenset()` |

Three value edits the codemod cannot make. The first two because `from pyjinhx import discovery`
is recorded by the test as an import of `pyjinhx`:

- `components.classless`: replace `"pyjinhx"` with `"pyjinhx.components"`.
- `reactive.fanout`: replace `"pyjinhx"` with `"pyjinhx.components"` and
  `"pyjinhx.rendering"`.
- `rendering.pipeline`: the codemod leaves `"pyjinhx.rendering.template_context"`
  twice (once for markers, once for render_context); delete one (ruff B033
  reports it).

`__init__`'s entry becomes `{"pyjinhx.components.importer"}`; `config` keeps
`"pyjinhx"` for `from pyjinhx import dev`.

### 7.3 The invariant tests in the same file

| test (line) | change |
|---|---|
| module docstring (1-12) | new file names; drop the descriptor sentence |
| `test_descriptor_imports_nothing_from_pyjinhx` (854) | delete (the file is gone) |
| `test_segments_imports_nothing_from_pyjinhx` (858) | path `rendering/segments.py` |
| `test_component_is_the_only_importer_of_class_descriptor` (862) | rewrite: no module under `pyjinhx/` other than `components/base.py` has an `ImportFrom` naming `ClassDescriptor` |
| `test_session_never_reaches_into_reactive` (874) | path `rendering/session.py`; the allowed set is rewritten by the codemod |
| `test_nothing_below_config_imports_config` (891) | expected set: `render_cache` -> `rendering.render_cache`, `session` -> `rendering.session` |
| `test_nothing_imports_context` (938) | unchanged, and still true |
| `test_component_only_imports_render_and_session_inside_a_method_body` (969) | path `components/base.py`; names rewritten by the codemod |
| `test_importer_only_imports_component_inside_a_function` (982) | path `components/importer.py` |
| `test_session_only_imports_config_…` (990) | path `rendering/session.py` |
| `test_render_cache_only_imports_config_…` (1022) | path `rendering/render_cache.py` |
| `test_props_header_only_imports_component_…` (1057) | path `components/props_header.py` |
| `RENDER_SPINE_MODULES` (1087) | `("components.base", "rendering.pipeline", "rendering.root_attrs", "rendering.segments", "rendering.session", "rendering.template_context")` |
| `test_render_spine_modules_do_not_import_reactive_on_disk` (1100) | `PACKAGE_ROOT / f"{stem.replace('.', '/')}.py"` |

Add one test, because the rule now carries the design: every module under
`pyjinhx/document/` has `internal_imports(path) <= {"pyjinhx.document.scanner"}`.

Test count: baseline minus 2. In this file: -1 (`test_descriptor_imports_nothing…`
deleted), -2 (the spine parametrization goes 8 -> 6), +3 and -2 (the per-module
parametrization gains three `__init__.py` and loses the two folded files), +1
(the new `document/` test) = -1. In `test_descriptor.py`: -1 (7.4). Record the
baseline before step 1 and check the delta is exactly that. (The prototype
deleted the class-descriptor test instead of rewriting it and had no `document/`
test, and collected 6293 against 6296, as that arithmetic predicts.)

### 7.4 Other tests that name modules as strings, paths or objects

All under `tests/pyjinhx/` today; re-locate after tests-layout with
`grep -rn "<quoted text>" tests`.

| where | what | action |
|---|---|---|
| `test_descriptor.py:172` `test_descriptor_module_is_import_pure` | reads the source of `pyjinhx.descriptor` | delete; the other eleven tests in the file stay, now importing `ClassDescriptor` from `pyjinhx.components.base` |
| `test_props_header_parse.py:244` | `parents[2] / "pyjinhx" / "props_header.py"` | `… / "pyjinhx" / "components" / "props_header.py"` (and the `parents[n]` depth tests-layout gives it) |
| `test_assets.py:303` | `Path(pyjinhx.__file__).parent / "assets.py"` | `… / "rendering" / "assets.py"` (passes either way; keep it pointing at a real file) |
| `integrations/test_reactive_request_cycle.py:529-555` | `upper`, `lower`, `allowed_edges` name `pyjinhx.session`, `pyjinhx.context`, `pyjinhx.dev`, `pyjinhx.config` | codemod rewrites `pyjinhx.session`; the rest is unchanged. Read it once after: `upper` must still be config, context, dev, integrations |
| `test_component_descriptor.py:312-1105` (11 places) | `monkeypatch.setattr(pyjinhx._component, …)` | codemod (dotted name); needs `import pyjinhx.components.base` at the top, which the codemod also rewrites |
| `test_segments.py:124,875`, `test_component.py:573` | `inspect.getsource(pyjinhx.<module>)` | codemod |
| `test_discovery.py:134-252`, `test_pjx_python_component.py:359`, `test_classless_factory.py:273`, `test_config_v2.py:537` | import lines inside source strings written to temp modules | codemod (it matches inside string literals) |
| `tests/test_package_layout.py:163,165` | `importlib.import_module("pyjinhx.session")`, `("pyjinhx.segments")` | codemod |
| about 60 files | `from pyjinhx import discovery` (also `registry`, `sfc`, `rendering`, `assets`, `session as session_module`, `importer`, `classless`, `props_header`) | codemod splits the line by package and renames the module's uses in that file (`sfc.` -> `scanner.`, `rendering.` -> `pipeline.`) |

## 8. Everything else that names a module

Source (`pyjinhx/`, non-builtins), lines that hold an old dotted name, an old
path or `from pyjinhx import <moved>`; all rewritten by the codemod, listed so
the diff can be checked against it:

```
__init__.py           5 14 43 44 45 46 48 49 59        __init__.pyi  3 4 5 7 8 18 19
_component.py         6-9 34 35 36 44 48 49 143 458 496 553 736 740 741 907
assets.py             24 27 346   (+ line 30 by hand)   classless.py  11 22 23 29 30 31 32
client/inject.py      9 18                              config.py     28 29 30
context.py            14                                descriptor.py 4 35
dev.py                17 18                             discovery.py  17 18 33
importer.py           23 152 224                        manifest.py   55 131 384
markers.py            12                                props_header.py 36 42 45 183 185 229
registry.py           14 27 28                          render_cache.py 10 17 20
render_context.py     10 11                             rendering.py  15-21 32 33 34
responses.py          16 20 21                          root_attrs.py 4 5 8 11 24 92
segments.py           56                                session.py    13-17 22 28 505
stubgen.py            8 31                              template_blocks.py 26
integrations/base.py  84                                integrations/fastapi.py 15 34 35 36 101
reactive/assets.py    9 21 29                           reactive/cache.py 32
reactive/component.py 27 37                             reactive/fanout.py 37 43 44 45 46 245
reactive/mutations.py 13                                reactive/root_attrs.py 10 13 14 15
builtins/**           76 modules, `from pyjinhx._component import …`
```

Scripts (13 files, all `bench_*` plus `fold_components.py`):
`bench_parser_tagfree.py:30`, `bench_cross_request_load.py:32`,
`bench_cross_request_cache.py:38-39`, `bench_field_count.py:34,39-41`,
`bench_mixed_reactive_tree.py:33-37`, `bench_reactive_cache.py:25`,
`bench_render_scaling_v2.py:28-31`, `bench_render_scaling.py:22-23`,
`bench_render_depth.py:30-33,68`, `bench_reactive_fanout.py:59-60`,
`bench_slot_payload.py:6,43-46,121`, `fold_components.py:30,31,41`. Where a
script imported both `_component` and `descriptor` it ends with two
`from pyjinhx.components.base import` lines; join them by hand (five scripts).

Examples: `examples/todo/components/app/__init__.py:9`
(`from pyjinhx.classless import component`). Change it to
`from pyjinhx import component`: it is the public spelling of the same object and
an example should not show a deep import.

Docs (24 files changed by the codemod; no page is renamed, `mkdocs.yml` is not
touched):

- **mkdocstrings**: the plugin is enabled (`mkdocs.yml:43`) but no page holds a
  `::: pyjinhx…` directive today (`grep -rn "^::: " docs` is empty). If one
  appears before implementation, the codemod's dotted-name rule covers it, and
  `mkdocs build --strict` fails on a wrong path.
- `docs/hooks.py:13,14,17` (imports; runs at every docs build).
- `docs/api/`: `assets-api.md:7,58,94`, `base-component.md:43,67`,
  `cache-backends.md:6`, `cache-invalidation.md:7,15,43`,
  `client-backend.md:35,50,66`, `finder.md:61`,
  `mutations-keys-context.md:60`, `parser.md:23,56`, `reactive-api.md:54`,
  `registry.md:3,6,14,42,50,57`, `responses.md:3,8,84`.
- `docs/guide/`: `assets.md:149-308` (11 places), `configuration.md:37,51`,
  `registry.md:7-137` (8 places), `usage-tiers.md:56`.
- `docs/integrations/`: `claude-code.md:138,221,254-256`, `fastapi.md:162,167`,
  `htmx.md:389`. `docs/getting-started/build-an-app.md:11,117`.
  `docs/reactivity.md:278`.
- `docs/reference/public-api.md:5`: the list of internal modules becomes
  `pyjinhx.rendering.session`, `pyjinhx.rendering.assets`, `pyjinhx.client`,
  `pyjinhx.dev`, `pyjinhx.components.base`, `pyjinhx.reactive.*`.
- `docs/decisions/0003-builtin-css-ordering.md:32`
  (`pyjinhx.assets._is_builtin_asset`): updated, it describes the live mechanism.
- By hand, `docs/migration.md:917-919` ("`pyjinhx.render` -> `pyjinhx.rendering`",
  a 0.x -> 1.0 note): the codemod turns the target into
  `pyjinhx.rendering.pipeline`, which is right; reword the sentence so it does not
  read as if 1.0 had that path. `:72,128` (`pyjinhx.responses`) are plain renames.
- By hand, add to `docs/migration.md` a short "1.18: internal modules moved"
  section holding the table of section 3 as dotted names. The docs show about
  forty "not yet public" deep imports (`request_scope`, `all_assets`,
  `resolver_with_hash`, `register_instance`, `compose`, …) that readers have
  copied.
- Unchanged and correct: every `pyjinhx.dev`, `pyjinhx.manifest`,
  `pyjinhx.stubgen`, `pyjinhx/block_grammar.json` mention
  (`docs/reference/commands.md`, `docs/guide/components.md:476-538`,
  `docs/reactivity.md:613-630`, `docs/guide/configuration.md:147-151`,
  `docs/api/config.md:99`, `docs/api/mutations-keys-context.md:211,218`,
  ADR 0009).
- Not touched: `docs/superpowers/**` (the rebuild ADRs and plans are records of
  what was true when written) and `CHANGELOG.md` history.

`CHANGELOG.md`: a new top entry, "Changed": the module map, "the public API is
unchanged", `python -m pyjinhx.manifest|stubgen` unchanged, and the cache note of
section 6.

CI (`.github/workflows/`): nothing names a moved module. `tests.yml:60`
(`import pyjinhx; import pyjinhx.config`) and `:37` (`basedpyright pyjinhx/`)
hold. README.md names none.

## 9. tests/unit

Rule: `tests/unit/` mirrors `pyjinhx/`, so a test file follows its module, and a
test file named for a renamed module is renamed with it. If tests-layout kept
several files for one module, they move together into the module's directory and
only the one named exactly `test_<old module>.py` is renamed.

| module | `tests/unit/…` before this plan | after |
|---|---|---|
| `document/scanner.py` | `test_sfc*.py` (`test_sfc_extract`, `_header`, `_python_block`) | `document/test_scanner*.py` |
| `document/template_blocks.py` | `test_template_blocks.py` | `document/test_template_blocks.py` |
| `components/base.py` | `test_component.py`, `test_component_descriptor.py`, `test_descriptor.py`, `test_children_field_resolution.py` | `components/test_base.py` and the same names under `components/`; `test_descriptor.py` becomes `components/test_class_descriptor.py`, or its eleven remaining tests are appended to the base file if tests-layout holds strictly one file per module |
| `components/classless.py` | `test_classless_*.py` | `components/` |
| `components/discovery.py` | `test_discovery*.py`, `test_block_discovery.py`, `test_registry.py` (it tests the *class* registry), `test_replace.py`, `test_orphan_tags.py` | `components/` |
| `components/importer.py` | `test_importer.py` | `components/` |
| `components/props_header.py` | `test_props_header_*.py`, `test_stale_header_warning.py` | `components/` |
| `rendering/pipeline.py` | `test_rendering.py` or `test_render_{children,cycle_guard,hook,instantiate,integration,level,nested_integration,public,splice}.py`, `test_direct_nesting.py` | `rendering/test_pipeline.py`, or the same names under `rendering/` |
| `rendering/session.py` | `test_session.py`, `test_loader.py` | `rendering/` |
| `rendering/template_context.py` | `test_markers.py`, `test_render_context.py`, `test_slot_*.py` | `rendering/test_template_context.py` (markers + render_context joined), `rendering/test_slot_*.py` |
| `rendering/segments.py` | `test_segments*.py` | `rendering/` |
| `rendering/root_attrs.py` | `test_root_attrs.py` | `rendering/` |
| `rendering/assets.py` | `test_asset*.py` | `rendering/` |
| `rendering/render_cache.py` | `test_render_cache_*.py`, `test_render_cost_threshold.py` | `rendering/` |
| `rendering/registry.py` | `test_instance_registry.py` | `rendering/test_registry.py` |
| `integrations/responses.py` | `test_responses.py`, `test_compose_fanout.py` | `integrations/` |
| `config`, `context`, `app_context`, `dev`, `manifest`, `stubgen`, `reactive/*`, `integrations/*`, `client/*`, `builtins/*` | wherever tests-layout put them | unchanged |
| the whole package | `test_import_graph.py`, `test_package_layout.py` | unchanged place; contents per section 7 |

Two things to settle with the tests-layout convention before moving:

1. **Basenames collide.** `components/test_base.py` vs the existing
   `integrations/test_base.py`; `rendering/test_registry.py` vs
   `integrations/test_registry.py`; `rendering/test_root_attrs.py` and
   `rendering/test_assets.py` vs any `reactive/` file of that name (today those
   are spelled `test_reactive_root_attrs.py` to dodge exactly this). pytest's
   default import mode needs either unique basenames or an `__init__.py` in each
   test directory (`tests/pyjinhx/integrations/` and `client/` have one,
   `reactive/` does not). Give `tests/unit/{document,components,rendering}/` an
   `__init__.py` if tests-layout's directories have them; otherwise keep distinct
   basenames (`test_instance_registry.py` stays as it is, the base file is
   `test_component_base.py`).
2. **`conftest.py` and path depth.** Fixtures in `tests/unit/conftest.py` reach a
   subdirectory by inheritance, but any `Path(__file__).parents[n]` in a moved
   test gains one level (`test_props_header_parse.py:244` is the known one;
   `grep -rn "parents\[" tests/unit` after the move).

## 10. Steps

Each step is one commit. Steps 1 and 2 leave the package unimportable on purpose
(pure renames first, so the rename is unmistakable in history); the gate first
runs at the end of step 3. Nothing is pushed between them.

**0. Baseline** (after rebasing onto the merged master; no commit)

```
uv sync
uv run pytest -q 2>&1 | tail -1                       > $T/pytest.before
uv run pytest --collect-only -q 2>&1 | tail -1        > $T/collect.before
uv run python -m pyjinhx.manifest --grammar | sha256sum > $T/grammar.before
uv run python -m pyjinhx.manifest examples pyjinhx/builtins > $T/manifest.before.json
uv run python -c "import pyjinhx, pyjinhx.builtins as b; print(sorted(pyjinhx.__all__)); print([(n, type(getattr(pyjinhx, n)).__name__) for n in sorted(pyjinhx.__all__)]); print(sorted(b.__all__))" > $T/api.before
for i in 1 2 3 4 5; do uv run python -X importtime -c "import pyjinhx" 2>&1 | tail -1; done > $T/importtime.before
uv run python -c "import sys, pyjinhx; print(sorted(m for m in sys.modules if m.startswith('pyjinhx')))" > $T/modules.before
uv build --wheel -o $T/wheel.before && unzip -Z1 $T/wheel.before/*.whl | sort > $T/wheel.before.txt
```

`$T` is a scratch directory outside the repository. Save the codemod of
appendix A there as `$T/relayout_codemod.py`.

**1. Move the files** (`git mv` only, no content change)

```
mkdir pyjinhx/document pyjinhx/components pyjinhx/rendering
git mv pyjinhx/sfc.py             pyjinhx/document/scanner.py
git mv pyjinhx/template_blocks.py pyjinhx/document/template_blocks.py
git mv pyjinhx/_component.py      pyjinhx/components/base.py
git mv pyjinhx/descriptor.py      pyjinhx/components/descriptor.py
git mv pyjinhx/classless.py pyjinhx/discovery.py pyjinhx/importer.py pyjinhx/props_header.py pyjinhx/components/
git mv pyjinhx/rendering.py       pyjinhx/rendering/pipeline.py
git mv pyjinhx/session.py pyjinhx/render_cache.py pyjinhx/assets.py pyjinhx/segments.py pyjinhx/root_attrs.py pyjinhx/registry.py pyjinhx/rendering/
git mv pyjinhx/markers.py         pyjinhx/rendering/template_context.py
git mv pyjinhx/render_context.py  pyjinhx/rendering/render_context.py
git mv pyjinhx/responses.py       pyjinhx/integrations/responses.py
touch pyjinhx/document/__init__.py pyjinhx/components/__init__.py pyjinhx/rendering/__init__.py
git add pyjinhx
```

Verify: `git status --short | grep -v '^R' ` shows only the three new
`__init__.py`; `git diff --cached -M --stat | tail -1` reports 0 insertions,
0 deletions.

**2. Merge** (section 4)

Fold `components/descriptor.py` into `components/base.py` and
`rendering/render_context.py` into `rendering/template_context.py`;
`git rm` the two emptied files. Change `rendering/assets.py:30` to
`.parent.parent`. Verify: `uv run python -m py_compile pyjinhx/components/base.py
pyjinhx/rendering/template_context.py pyjinhx/rendering/assets.py`;
`git diff --cached -M --stat` shows `markers.py => rendering/template_context.py`
and `_component.py => components/base.py` still detected as renames.

**3. Fix every reference**

```
python $T/relayout_codemod.py pyjinhx tests scripts docs examples README.md mkdocs.yml .github
uv run ruff check --fix .        # re-sorts the imports the rewrite reordered (about 110 files) and drops the B033 duplicate
uv run ruff format .
```

Then the hand edits the codemod cannot make:
`test_import_graph.py` keys, the three value edits and the invariant tests
(7.2, 7.3); the three rows of 7.4 marked delete or path, and the read-through of
the layering test; the example import and
the doubled script imports (section 8); the `scanner.py`, `base.py` and
`template_context.py` module docstrings.

Verify:

```
uv run pytest -q 2>&1 | tail -1                       # no failures; passed = before - 2 (section 7.3), skips and xfails as before
grep -rnP "(?<![\w.])pyjinhx[./](sfc|template_blocks|props_header|segments|root_attrs|markers|_component|descriptor|classless|registry|discovery|importer|session|render_cache|assets|responses|render_context)\b" \
  pyjinhx tests scripts docs examples README.md --exclude-dir=superpowers --exclude-dir=__pycache__   # empty
grep -rnE "from pyjinhx import .*\b(discovery|sfc|classless|importer|props_header|registry|rendering|session|assets|segments|markers)\b" pyjinhx tests scripts docs examples   # empty
uv run python -m pyjinhx.manifest --grammar | sha256sum | diff - $T/grammar.before
uv run python -m pyjinhx.manifest examples pyjinhx/builtins | diff - $T/manifest.before.json
  # only "line" values inside files whose own import lines this step re-sorted or re-spelled
  # (in the prototype: examples/todo/components/app/__init__.py, 5 values); no name, prop, kind or diagnostic differs
uv run python -m pyjinhx.stubgen --check examples; echo $?        # same exit code as on master
uv run python -c "import pyjinhx, pyjinhx.builtins as b; print(sorted(pyjinhx.__all__)); print([(n, type(getattr(pyjinhx, n)).__name__) for n in sorted(pyjinhx.__all__)]); print(sorted(b.__all__))" | diff - $T/api.before
uv run python -c "import sys, pyjinhx; assert 'pydantic' not in sys.modules and 'jinja2' not in sys.modules; print(sorted(m for m in sys.modules if m.startswith('pyjinhx')))"
  # exactly: pyjinhx, pyjinhx.components, pyjinhx.components.importer, pyjinhx.document, pyjinhx.document.scanner
uv run python -c "import sys; from pyjinhx import manifest, stubgen; assert 'pydantic' not in sys.modules and 'jinja2' not in sys.modules"
for i in 1 2 3 4 5; do uv run python -X importtime -c "import pyjinhx" 2>&1 | tail -1; done   # within noise of importtime.before
for m in components.base components.classless components.discovery components.importer components.props_header \
         document.scanner document.template_blocks rendering.pipeline rendering.session rendering.template_context \
         rendering.segments rendering.root_attrs rendering.assets rendering.render_cache rendering.registry \
         integrations.responses reactive.fanout reactive.component config context dev manifest stubgen; do
  uv run python -c "import pyjinhx.$m" || echo "CYCLE OR BREAK: $m"; done      # prints nothing
uvx "basedpyright==1.39.9" pyjinhx/ | tail -1                                    # 0 errors
```

**4. Move the unit tests** (section 9): `git mv` only, plus `__init__.py` or
renames per the tests-layout convention, plus any `parents[n]` depth, plus the
two joins of section 9 (markers + render_context tests; descriptor tests) if the
one-file-per-module rule requires them. Verify:
`uv run pytest -q | tail -1` equals step 3's line;
`uv run pytest --collect-only -q | tail -1` equals step 3's count; no
"import file mismatch" in the output.

**5. Docs by hand** (section 8): the `migration.md` section and rewording,
`public-api.md:5` read-through. Verify: `uv run mkdocs build --strict` (with
`docs/superpowers` moved out and back); `uv run pytest -q` on the docs tests
(`test_docs_*.py`, `test_package_layout.py`, `test_gallery_demos.py`).

**6. CHANGELOG** entry (section 8). No version bump in this branch; the release
does that.

**7. Final gate and package check**

```
uv run ruff format --check . && uv run ruff check . && uv run pytest -q
uv build --wheel -o $T/wheel.after && unzip -Z1 $T/wheel.after/*.whl | sort > $T/wheel.after.txt
diff <(grep -v '\.py$' $T/wheel.before.txt) <(grep -v '\.py$' $T/wheel.after.txt)   # empty: every data file ships
diff $T/wheel.before.txt $T/wheel.after.txt   # only the moves of section 3, +3 __init__.py, -descriptor.py, -render_context.py
python -m venv $T/venv && $T/venv/bin/pip install -q $T/wheel.after/*.whl && cd $T && \
  $T/venv/bin/python -m pyjinhx.manifest --grammar | sha256sum | diff - grammar.before && \
  $T/venv/bin/python -c "from pyjinhx import BaseComponent, render, setup; from pyjinhx.builtins import PJXBadge; print(PJXBadge(label='x').render()[:40])"   # <span id="pjx-1" class="pjx-badge …
```

and, read-only, in a pjx-ls checkout: `node scripts/sync-pyjinhx.mjs --check
<this worktree>` does not fail on a missing `pyjinhx/block_grammar.json` (it may
report corpus drift if tests-layout moved `tests/fixtures/block_grammar/`, which
is that branch's to settle), and its manifest-runner test passes against an
interpreter that has this wheel.

## 11. Risks

1. **`pyjinhx.rendering` is an old module name and the new package name.** A
   stale `from pyjinhx.rendering import render_level` is an `ImportError`, which
   is intended; a stale `import pyjinhx.rendering as r` succeeds and fails at
   `r.render`. The codemod cannot tell a rewritten `pyjinhx.rendering` from an
   unrewritten one in every context, so it runs once and refuses a second run.
   The residue greps of step 3 do not cover this name; check it with
   `grep -rnP "pyjinhx\.rendering\b(?!\.(pipeline|session|template_context|segments|root_attrs|assets|render_cache|registry)\b)" pyjinhx tests scripts docs examples`
   and read each hit (expected: the two `"pyjinhx.rendering"` allow-list strings
   and `from pyjinhx.rendering import registry`-style lines).
2. **Open branches.** There are dozens of worktrees. Any branch that adds an
   import of a moved module keeps the old spelling after a rebase, and git's
   rename detection does not help with a *new* line. Land this when the three
   named branches are in and little else is open, and tell branch owners to run
   the codemod of appendix A on their branch after rebasing, on the files the
   branch touched only: `python relayout_codemod.py --force $(git diff
   --name-only master...)`, then read the diff. Keep the script in the PR
   description for that reason.
3. **`assets.py:30`** (section 6). One forgotten line silently reorders CSS; a
   test catches it, and step 2 names it.
4. **A re-export in a new `__init__.py`.** It would look harmless and would make
   `import pyjinhx` load pydantic and jinja2. The allow-list entries
   `frozenset()` for the three `__init__` keys and the step-3 module-list check
   both fail on it.
5. **Hoisting a function-local import while tidying.** The cycles
   (`base` <-> `pipeline`/`session`, `importer` <-> `base`, `props_header` <->
   `base`, `assets` <-> `base`) are held open only by those imports being inside
   functions. `ruff check --fix` does not move them; a person might. The
   `test_*_only_imports_*_inside_a_function_body` tests cover five of them.
6. **Running tests with another checkout's interpreter.** Subprocess tests
   (`test_bench_scripts_smoke.py`, `test_fold_script.py`,
   `test_pjx_python_component.py::test_python_dash_m_…`) import the installed
   pyjinhx. In the prototype, run from a copy with the main checkout's venv, 15
   of them failed for that reason alone and passed with the copy on `PYTHONPATH`.
7. **Stale pickles in a persistent cache** (section 6): misses and one warning,
   not errors; documented in the CHANGELOG.
8. **Users on the documented "not yet public" deep imports** break on upgrade.
   This is the approved clean break; the `migration.md` table is the mitigation.
9. **Count drift.** If flatten-builtins or tests-layout change how
   `test_import_graph.py` parametrizes, the "-2" of section 7.3 changes; derive
   it again from the itemization there instead of trusting the number.

## 12. Open questions

- **Q1. The three-way context merge was not done.** If it is still wanted:
  create `rendering/context.py` from `context.py` + `app_context.py` +
  `template_context.py`'s `build_context` half, then delete
  `test_nothing_imports_context`, drop `pyjinhx.context` from `upper` in
  `test_lower_layers_do_not_import_the_wiring_layer`, give `reactive.component`
  the edge to it, and accept that `from pyjinhx import AppContext` loads jinja2
  and pydantic (today it loads only the stdlib). No cycle results. A middle
  path that breaks fewer rules: merge only `AppContext` into `context.py`
  (one file fewer, one rule relaxed: `reactive.component` may import
  `pyjinhx.context`).
- **Q2. No `tools/`.** If wanted, section 5 has the forwarders; `dev.py` should
  still not go there.
- **Q3. `document/` holds two modules.** It earns the directory by being the
  only package with no outgoing edge; if two files do not justify a package,
  fold both into `components/` (one line each in the codemod's `MOVES`) and drop
  the added `document/` test.
- **Q4. Names**: `components/base.py`, `rendering/pipeline.py`,
  `rendering/template_context.py`, `document/scanner.py`. Each is one value in
  `MOVES`/`BARE`.
- **Q5. `responses` in `integrations/`, `registry` in `rendering/`** rather than
  the sketch's `rendering/` and `components/`.
- **Q6. Should `request_scope`, `all_assets`, `resolver_with_hash` and friends
  get a public spelling** before their paths move under users? Out of scope
  here; it would turn most of the docs churn into a one-time fix.
- **Q7. tests-layout's plan was not available.** Section 9's "before" column is
  inferred from "one file per module"; confirm the directory convention
  (`__init__.py` or unique basenames) before step 4.
- **Q8. An ADR for the layout?** Not planned: the rule fits in the three
  docstring-less `__init__.py` files' absence of content and in
  `test_import_graph.py`'s comments. Say so if a `docs/decisions/0010` is wanted
  (`test_every_adr_is_indexed_and_in_nav` then needs the index and nav lines).

Not in this plan, noted for later: `components/classless.py` imports one regex
(`RE_PASCAL_CASE_TAG_NAME`) from `rendering/segments.py`, the only module-scope
edge from `components/` up into `rendering/`; the constant belongs with the
naming rules in `document/scanner.py`. And `_pascal_to_snake` is a private alias
of `scanner.pascal_to_snake` that seven outside files import.

## Appendix A — the codemod

Prototyped on a copy of master `ed7e97b5`: applied after the moves and merges it
changed 356 files; with the hand edits of step 3 the non-browser suite matched
the baseline (4476 passed before; after, every test passed except the deleted
ones and the environment-bound subprocess tests of risk 6, which passed with the
copy on `PYTHONPATH`; the 83 browser-driven test files were collected, not run), `basedpyright` reported 0 errors, `mkdocs build --strict`
passed, and all 6293 remaining tests collected.

```python
"""Rewrite references to the flat pyjinhx modules to the subpackage layout.

    python relayout_codemod.py [--check] [--force] PATH [PATH ...]

Rewrites, in every .py/.pyi/.md/.yml/.toml/.pjx file under the paths:
  1. dotted names           pyjinhx.session        -> pyjinhx.rendering.session
  2. `from pyjinhx import`  discovery, sfc         -> from pyjinhx.components import discovery ...
  3. file paths             pyjinhx/session.py     -> pyjinhx/rendering/session.py
  4. bare renamed files     sfc.py, _component.py  -> scanner.py, base.py
Run it once, from the repository root, after the files have moved. It refuses
a second run (`pyjinhx.rendering` is both an old module and the new package, so
a rewritten tree cannot be told from an unrewritten one everywhere). --check
lists what would change and writes nothing. --force skips that refusal, for a
branch rebased onto the new layout: pass only the files the branch touched and
read every `pyjinhx.rendering` line in the diff.
"""

import re
import sys
from pathlib import Path

# old top-level module -> (new package, new module name)
MOVES = {
    "sfc": ("pyjinhx.document", "scanner"),
    "template_blocks": ("pyjinhx.document", "template_blocks"),
    "_component": ("pyjinhx.components", "base"),
    "descriptor": ("pyjinhx.components", "base"),
    "classless": ("pyjinhx.components", "classless"),
    "discovery": ("pyjinhx.components", "discovery"),
    "importer": ("pyjinhx.components", "importer"),
    "props_header": ("pyjinhx.components", "props_header"),
    "rendering": ("pyjinhx.rendering", "pipeline"),
    "session": ("pyjinhx.rendering", "session"),
    "render_cache": ("pyjinhx.rendering", "render_cache"),
    "assets": ("pyjinhx.rendering", "assets"),
    "segments": ("pyjinhx.rendering", "segments"),
    "root_attrs": ("pyjinhx.rendering", "root_attrs"),
    "markers": ("pyjinhx.rendering", "template_context"),
    "render_context": ("pyjinhx.rendering", "template_context"),
    "registry": ("pyjinhx.rendering", "registry"),
    "responses": ("pyjinhx.integrations", "responses"),
}
RENDERING_CHILDREN = sorted({n for p, n in MOVES.values() if p == "pyjinhx.rendering"})

_names = "|".join(sorted(MOVES, key=len, reverse=True))
# `pyjinhx.rendering` is both an old module and the new package: leave it alone
# where one of the package's own modules already follows.
_children = "|".join(RENDERING_CHILDREN)
DOTTED = re.compile(
    rf"(?<![\w.])pyjinhx\.({_names})\b"
    rf"(?!\.(?:{_children})\b)(?! import (?:{_children})\b)"
)
PATHS = re.compile(rf"(?<![\w.])pyjinhx/({_names})\.py\b")
BARE = {  # file names that changed, not just moved; only outside a path
    "sfc.py": "scanner.py",
    "_component.py": "base.py",
    "descriptor.py": "base.py",
    "rendering.py": "pipeline.py",
    "markers.py": "template_context.py",
    "render_context.py": "template_context.py",
}
BARE_RE = re.compile(r"(?<![\w/.])(" + "|".join(map(re.escape, BARE)) + r")\b")
FROM_ROOT = re.compile(
    r"^(?P<indent>[ \t]*[\"']?)from pyjinhx import (?P<names>[\w ,]+?)"
    r"(?P<tail>(?:\\n)?[\"']?[,)]?[ \t]*(?:#.*)?)$",
    re.MULTILINE,
)


def _dotted(match: re.Match[str]) -> str:
    package, name = MOVES[match.group(1)]
    return f"{package}.{name}"


def _path(match: re.Match[str]) -> str:
    package, name = MOVES[match.group(1)]
    return f"{package.replace('.', '/')}/{name}.py"


def _from_root(text: str) -> str:
    renamed: dict[str, str] = {}

    def split(match: re.Match[str]) -> str:
        parts = [p.strip() for p in match.group("names").split(",") if p.strip()]
        keep: list[str] = []
        moved: dict[str, list[str]] = {}
        for part in parts:
            name, _, alias = part.partition(" as ")
            name, alias = name.strip(), alias.strip()
            if name not in MOVES:
                keep.append(part)
                continue
            package, new = MOVES[name]
            if alias:
                moved.setdefault(package, []).append(f"{new} as {alias}")
            else:
                moved.setdefault(package, []).append(new)
                if new != name:
                    renamed[name] = new
        if not moved:
            return match.group(0)
        indent, tail = match.group("indent"), match.group("tail")
        lines = []
        if keep:
            lines.append(f"{indent}from pyjinhx import {', '.join(keep)}")
        for package in sorted(moved):
            names = ", ".join(sorted(dict.fromkeys(moved[package])))
            lines.append(f"{indent}from {package} import {names}")
        return "\n".join(lines) + tail

    text = FROM_ROOT.sub(split, text)
    for old, new in renamed.items():
        # the module object's uses in this file: `sfc.python_block(...)`
        text = re.sub(rf"(?<![\w.]){re.escape(old)}\.(?=[A-Za-z_])", f"{new}.", text)
        text = re.sub(rf"(?<=\()\s*{re.escape(old)}(?=,)", new, text)
    return text


def rewrite(text: str, is_python: bool) -> str:
    text = DOTTED.sub(_dotted, text)
    text = PATHS.sub(_path, text)
    text = BARE_RE.sub(lambda m: BARE[m.group(1)], text)
    if is_python:
        text = _from_root(text)
    return text


SUFFIXES = {".py", ".pyi", ".md", ".yml", ".yaml", ".toml", ".pjx", ".json"}
SKIP = {".git", ".venv", "node_modules", "__pycache__", "site", "superpowers"}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    init = Path("pyjinhx/__init__.py")
    if not init.is_file():
        print("run from the repository root", file=sys.stderr)
        return 2
    applied = "pyjinhx.rendering.pipeline" in init.read_text(encoding="utf-8")
    if applied and not check and "--force" not in argv:
        print("already applied; --force to rewrite named files anyway", file=sys.stderr)
        return 2
    changed = 0
    for root in [Path(a) for a in argv if not a.startswith("--")]:
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for file in files:
            if not file.is_file() or file.suffix not in SUFFIXES:
                continue
            if SKIP & set(file.parts) or file.name == "CHANGELOG.md":
                continue
            old = file.read_text(encoding="utf-8")
            new = rewrite(old, file.suffix in {".py", ".pyi"})
            if new != old:
                changed += 1
                print(file)
                if not check:
                    file.write_text(new, encoding="utf-8")
    print(f"{changed} file(s) {'would change' if check else 'changed'}")
    return 1 if check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Known limits, all covered by step 3's greps: a parenthesised multi-line
`from pyjinhx import (…)` is not split (the one that exists today,
`docs/integrations/claude-code.md:232`, names only public symbols); a local variable that happens to be called `sfc` or
`rendering` in a file that also imports that module from the package root would
be renamed with it (none found in the prototype).
