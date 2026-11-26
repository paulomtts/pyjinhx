# A `{#python … #}` block in `.pjx` files — implementation plan

Spec: `docs/superpowers/specs/2026-11-26-pjx-python-block-design.md`.
ADR draft: `docs/superpowers/rebuild/adr/0015-a-pjx-document-may-carry-its-class.md`.
Editor follow-up (not in this PR): `docs/superpowers/specs/2026-11-26-pjx-ls-followup.md`.
Prior art to mine, not to copy: commit `328ed733` (v0.x, PR #128):
`pyjinhx/importer.py`, `pyjinhx/sfc.py`, `pyjinhx/stubgen.py` and their tests
(`git show 328ed733:<path>`). v2 internals differ; the spec says where.

Branch: **`feat/ff-pyblock`**, off `feat/fewer-files` (PR #1075). Work in the
worktree `.claude/worktrees/ff-pyblock`.

## Ground rules for every task

- Strict TDD: write the listed tests first, watch them fail for the stated
  reason, then implement. One granular commit per green step.
- Small, human-looking code. No new abstraction unless two callers exist.
  Docstrings say what; comments say why; no PR or issue numbers in code.
- A new module, or a new import between pyjinhx modules (function-local ones
  included), must be declared in `tests/pyjinhx/test_import_graph.py`
  (`ALLOWED_INTERNAL_IMPORTS`) in the same commit.
- `pyjinhx/sfc.py`, `pyjinhx/importer.py`, `pyjinhx/stubgen.py` and
  `pyjinhx/manifest.py` are **stdlib-only at module scope**. `import pyjinhx`
  must not start importing pydantic or jinja2 (if no test pins that today,
  task 2 adds one).
- Nothing in tasks 1, 6 and 7 may import or run a block. Each of those tasks
  has a test whose block would write a sentinel file if it ran.
- Gate before a task is done, from the worktree root:
  `uv run ruff format` · `uv run ruff check` · `uv run pytest -q` (about six
  minutes, no xdist; run the task's own test files first) ·
  `uvx basedpyright` (no new errors) · for tasks that touch `docs/` outside
  `docs/superpowers`: `uv run mkdocs build --strict` with `docs/superpowers`
  moved out of `docs/` for the duration and moved back afterwards (move,
  never delete).
- Never `git stash`, never `git reset --hard`. Do not push, open a PR, or
  touch `master`. `docs/superpowers/*` is git-ignored except `rebuild/`, so
  files there need `git add -f`.
- Commit messages end with a blank line and
  `Co-Authored-By: <the implementing model> <noreply@anthropic.com>`.
- The real consumer app and the pjx-ls repository are read-only.

## Order and dependencies

```
1 ─┬─ 2 ── 3 ── 4 ── 5 ── 8 ─┐
   └─ 6 ── 7 ────────────────┴─ 9 ── 10 ── 11
```

After task 1 there are two independent chains (run time: 2–5, 8; tooling:
6–7) that can be worked in parallel worktrees. Within a chain the order is
fixed: the tasks edit the same files.

| # | Task | Model |
|---|---|---|
| 1 | Block scanner, line padding, conformance corpus | Opus |
| 2 | Import hook: finder, loader, install | Opus |
| 3 | Binding and refusals at class creation; render | Opus |
| 4 | Discovery: `import_document`, eager at `setup()`, lazy on a tag miss | Opus |
| 5 | Changed-block warning on template reload | Opus |
| 6 | Stub generator | Opus |
| 7 | Manifest, grammar data file | Opus |
| 8 | Fold script: `pyblock` subcommand | Sonnet |
| 9 | User docs, changelog, ADRs | Sonnet |
| 10 | Fourth shape in the parity fixture | Opus |
| 11 | Consumer trial re-run | Opus |

---

## Task 1 — block scanner, line padding, conformance corpus (Opus)

Spec "Block grammar", "Line numbers are the file's", "A shared conformance
corpus". Files: `pyjinhx/sfc.py`, `pyjinhx/template_blocks.py`,
`tests/pyjinhx/test_sfc_python_block.py` (new),
`tests/pyjinhx/test_template_blocks.py`, `tests/fixtures/block_grammar/`
(new), `tests/pyjinhx/test_block_grammar_corpus.py` (new).

Tests first:

- `sfc.python_block(source, filename)` on the spec's example returns the
  opener line, the body's first and last line, the closer line, and the body
  text. `None` when the document has no block.
- `sfc.python_source(source, filename)` returns the body padded with one
  newline per line above it: `ast.parse` of it puts `class TodoCount` on the
  line it has in the file, and a name's `col_offset` is its column in the
  file. A block that is not first in the document (markup and a `{#css#}`
  block above it) keeps the same property.
- Not a block, returns `None`: `{# python` (spaced); `{#python x = 1 #}` on
  one line; `{#-python`; `{#pythonic`.
- `SyntaxError`, each with `filename` and the right `lineno`: opener not in
  column 0; a second `python` block (line of the second); the first `#}` not
  alone on its line, for a string `"#}"`, for `f"{n:#}"` and for a trailing
  comment, with a message that names the fix; text after the closer on its
  line.
- A body line that is exactly `#}` ends the block there. `python_block`
  returns the short block; `template_blocks.inline_assets` (or whichever
  function task 3 ends up calling at registration) raises the existing
  stray-`#}` `TemplateSyntaxError` at the real closer's line. Extend the
  stray check to run when a document has a `python` block, not only css/js.
- `hide_block_lines`: a `python` block alone on its lines renders as nothing.
  Render `"{#python\nx = 1\n#}\n<p>hi</p>"` through a bare Jinja environment
  after `hide_block_lines` and get exactly `<p>hi</p>`; line numbers of the
  markup are unchanged (a template error on the `<p>` line reports line 4).
- `find_block(source, "css", …)` on a document whose Python body contains the
  text `{#css` inside a string still finds only the real css block.
- CRLF line endings: same blocks, same line numbers.
- Corpus: `tests/fixtures/block_grammar/` holds `<case>.pjx` plus
  `<case>.json` (`{"blocks": [{"keyword", "open_line", "body_lines",
  "close_line"}], "error": null | {"code", "line"}}`). One parametrised test
  scans every case with the real scanners (`find_block` for def/css/js,
  `python_block` for python) and compares. Cases: every one listed in the
  spec section. Error codes are short stable strings
  (`python-block-early-close`, `second-block`, `opener-not-at-line-start`,
  `text-after-closer`, `stray-comment-close`); define them once as constants
  in `sfc.py` and use them for the manifest in task 7.

Implement: move `_COMMENT_RE` to `sfc.py` as `COMMENT_RE` (one definition of
Jinja's comment rule; `template_blocks` imports it, an edge that already
exists). Add `python_block` and `python_source` to `sfc.py`. Add `"python"`
to the keyword tuple in `hide_block_lines`. `sfc.py` stays stdlib-only: it
raises `SyntaxError(msg, (filename, lineno, offset, text))`, not Jinja's
error. Why Opus: line and column identity is the contract everything else in
this plan leans on, and the corpus becomes a cross-repository interface.

## Task 2 — import hook (Opus)

Spec "Import". Files: `pyjinhx/importer.py` (new), `pyjinhx/__init__.py`,
`tests/pyjinhx/test_importer.py` (new), `tests/pyjinhx/test_import_graph.py`,
`tests/test_package_layout.py` if it lists modules.

Fixtures are written into `tmp_path` as real packages (`pkg/__init__.py`,
`pkg/card.pjx`) with `tmp_path` put on `sys.path` by `monkeypatch.syspath_prepend`;
each test removes its modules from `sys.modules` afterwards (one fixture).

Tests first:

- `from pkg.card import Card` works; `Card.__module__ == "pkg.card"`;
  `sys.modules["pkg.card"].__file__` ends in `card.pjx`; `__spec__.origin` is
  the same path; `__package__ == "pkg"`.
- A relative import inside the block (`from .helpers import shout`) and a
  package `__init__.py` re-export (`from .card import Card`) both work.
- One `.pjx` block importing a class from another `.pjx` module works.
- A `.pjx` with no `python` block is not a module: `ModuleNotFoundError`.
- `pkg/card.py` beside `pkg/card.pjx`: `import pkg.card` gives the `.py`
  (the finder is never asked). Pin it; task 3 and 4 refuse the pair.
- The finder is the **last** entry of `sys.meta_path` after `import pyjinhx`;
  `install()` twice adds one; `uninstall()` removes it. Importing an ordinary
  module never calls `PjxFinder.find_spec` (spy on it).
- `import pyjinhx` in a fresh interpreter (subprocess) installs the finder and
  leaves `pydantic` and `jinja2` out of `sys.modules`.
- A syntax error on a known line of the block: `SyntaxError` with
  `filename` = the `.pjx` path and that `lineno`.
- A function in the block that raises: the traceback's last frame has the
  `.pjx` filename and the file's line number, and
  `traceback.format_exc()` contains that line's source text.
- `inspect.getsource` of a function defined in the block returns its text.
- `loader.get_source("pkg.card")` is `sfc.python_source` of the file;
  `python -m pkg.card` (subprocess, a block that prints under
  `if __name__ == "__main__":`) prints.
- No `__pycache__` entry is written for the `.pjx`.
- Refused with `ImportError` naming the file: no component class that snakes
  to the stem; two that do; a class in the block that assigns a `template`
  string; a first line that is the v0.x opener `{# python` (message says to
  remove the space). After a refused import the module is not in
  `sys.modules`.
- Extra classes are fine: a block defining `Card`, a helper function, a plain
  class and `class WideCard(Card)` imports, and `WideCard` renders `Card`'s
  markup (this last assertion may need task 3; if it fails for a reason task
  3 owns, move it there).
- Pickle and `copy.deepcopy` round-trip an instance; `pickle.loads` in a
  subprocess that imports only `pkg` works when `pkg/__init__.py` has
  `import pyjinhx`.
- `importer.loaded_document(path)` returns `(module_name, document_class)`
  for a loaded file and `None` otherwise.

Implement:

- `PjxFinder(importlib.abc.MetaPathFinder)`: for each entry of the given
  path (or `sys.path`), `<entry>/<last segment>.pjx`; read it; answer with
  `importlib.util.spec_from_file_location(fullname, path, loader=…)` only if
  `sfc.python_block` finds a block. Appended, never inserted at 0.
- `PjxLoader`: the code is compiled from `sfc.python_source` with the `.pjx`
  path as filename and `dont_inherit=True`; `get_source` returns the same
  text; `get_code` works for `runpy`; no bytecode cache. Subclassing
  `importlib.abc.SourceLoader` and overriding `source_to_code` is the
  shortest way; the constraints above are what matter.
- After the body runs: the three refusals, then record the document in one
  lock-guarded dict keyed by resolved path.
- `_pascal_to_snake` and `BaseComponent` are imported from
  `pyjinhx._component` inside the function that needs them.
- `pyjinhx/__init__.py` imports `pyjinhx.importer` and calls `install()`
  before it swaps its module object.

Why Opus: global import state, the loader protocol, and error paths that
must leave `sys.modules` clean.

## Task 3 — binding and refusals at class creation; render (Opus)

Spec "How the class and the markup bind", "A sibling `card.py`",
"Composition with everything else". Files: `pyjinhx/_component.py`,
`tests/pyjinhx/test_pjx_python_component.py` (new),
`tests/pyjinhx/test_component_descriptor.py`.

Tests first (same `tmp_path` package fixture as task 2):

- Descriptor of a `.pjx`-hosted `Card`: `template_path` is the `.pjx`,
  `inline_class is None`, `provenance["template"] is Card`. The number of
  `is_file` probes `_walk_template` makes for it is the same as for a split
  component (reuse the existing probe-count test's pattern).
- Rendering it gives the markup with no blank line where the block was, and
  byte-identical output to the same component written split.
- `{#css#}` and `{#js#}` blocks in the same document ship as `InlineAsset`s;
  a sibling `card.css` ships first.
- `class WideCard(Card)` in the same block, `class TallCard(Card)` in a
  `.py` module, and a `.pjx`-hosted class subclassing another `.pjx`-hosted
  class each render the parent's document. A subclass with its own `.pjx`
  renders its own.
- A `.pjx`-hosted `ReactiveComponent` with `react={…}` and `load()` renders
  and has its `_pjx_react_keys`.
- The render-cache key changes when the `.pjx` mtime changes; its identity
  part is `pkg.card.Card`.
- `TypeError` at class creation, each naming the file:
  - the document also has a `{#def … #}` header (and the legacy first-line
    `{# def`);
  - the document has no markup (only blocks, comments, whitespace);
  - `pkg/card.py` defines `Card` and `pkg/card.pjx` has a `python` block (the
    message names both files and says to remove one).
- Not refused: a plain shape-S pair where the `.pjx` has no `python` block
  (existing tests must pass unchanged, including the stale-header warning).

Implement in `_resolve_class_descriptor`, where `source` is already in hand:
when `inline_class is None`, `"{#python" in source` and
`sfc.python_block(source, …)` finds a block, run the three checks. The owner
to compare is the class the walk named, or the last ancestor when the walk
returned its unprobed candidate; compare `_defining_module_file(owner)` with
`template_path`, both resolved. No change to `_walk_template`. Why Opus:
`_resolve_class_descriptor` runs for every component class in every app, so
the fast path and the probe budget must not move.

## Task 4 — discovery (Opus)

Spec "Discovery". Files: `pyjinhx/sfc.py` (`module_name_for`),
`pyjinhx/importer.py` (`import_document`), `pyjinhx/config.py`,
`pyjinhx/classless.py`, `tests/pyjinhx/test_importer.py`,
`tests/pyjinhx/test_discovery.py`, `tests/pyjinhx/test_orphan_tags.py`,
`tests/pyjinhx/test_config*.py` (whichever covers `_register_components`).

Tests first:

- `sfc.module_name_for(path)`: `root/app/ui/card.pjx` with `__init__.py` in
  `app` and `app/ui` and none in `root` → `"app.ui.card"`. Pure path
  arithmetic: no import, no `sys.path` read.
- `import_document(path)` imports and returns the module; calling it twice
  executes the block once (the block appends to a list in a helper module).
- A document the test already imported under its name is returned as is.
- A document already loaded under a *different* name than the derived one
  (loaded through a second `sys.path` entry) is returned as loaded, not
  imported again.
- `card.py` or a `card/` package beside the `.pjx`: `ImportError` naming both
  paths.
- The derived top directory is not on `sys.path`: `ImportError` saying to
  import the module before `setup()`.
- `setup(components_root=root)` with a tree holding one `python`-block
  document nobody imported: afterwards `discovery.get_class("card")` is the
  class and it is in `BaseComponent.__subclasses__()`'s tree.
- `setup()` twice executes each block once.
- A block that calls `component("Note")` at import time, where `note.pjx` is
  a header-only template in the same tree, imports cleanly during `setup()`
  (this is why the registry is built before the imports).
- A block with an error fails `setup()` with the `.pjx` in the traceback.
- `discovery.build_registry` still opens no file (the existing
  `Path.read_text`-patched test passes unchanged).
- Lazy: after `build_registry(root, [])` only (no `setup()`), rendering a
  parent whose template contains `<Card title="x"/>` imports `card.pjx`,
  registers `Card` and renders it. `component("Card")` returns the same
  class. Two threads doing so end with one class and one execution.
- An orphan with a header and no block, and one with neither, behave exactly
  as before.

Implement:

- `import_document`: `loaded_document(path)` first; else
  `importlib.import_module(sfc.module_name_for(path))`; then check
  `module.__file__`.
- `config._register_components`: `build_registry`; then for each
  `discovery.walk_templates(root)` candidate whose text contains `{#python`
  and has a block, `import_document`; if the set of component classes grew,
  `build_registry` again.
- `classless`: where an orphan's file is read for its header, a `python`
  block takes the other branch: `import_document`, then register the
  document class through `_register_first`. The import happens outside
  `_build_lock`, as header resolution already does.
- Leave `reactive/fanout.py` alone.

Why Opus: publish atomicity, the lock, re-entrant imports during `setup()`
and the "never twice" guarantee.

## Task 5 — changed-block warning on template reload (Opus)

Spec "Hot reload, honestly". Files: `pyjinhx/importer.py`,
`pyjinhx/session.py`, `tests/pyjinhx/test_loader.py`,
`tests/pyjinhx/test_pjx_python_component.py`.

Tests first:

- Render a `.pjx`-hosted component, rewrite the file changing only markup,
  bump its mtime, render again: new markup, no warning.
- Rewrite changing the block's body: the next render logs one warning naming
  the file and saying a restart applies it; the component still renders with
  the class it imported. A third render with no further edit logs nothing.
- A further edit to the block warns again (once).
- A `.pjx` with a block that was never imported through the hook (read as a
  plain template) logs nothing.

Implement: the importer keeps the body text it executed next to the loaded
record and exposes `block_changed(path, source) -> bool`.
`AbsolutePathLoader.get_source` calls it after reading a document that
contains `{#python`, and logs through the `pyjinhx` logger, remembering the
last text it warned about. `session → importer` is a new edge.

## Task 6 — stub generator (Opus)

Spec "Type-checking: stubs". Files: `pyjinhx/stubgen.py` (new),
`tests/pyjinhx/test_stubgen.py` (new).

Tests first:

- `generate_stub(source, filename)` for the spec's example: the result
  parses; every `ClassDef`, `FunctionDef` and annotated assignment has the
  same `lineno` as in `sfc.python_source(source)`; function bodies are
  `...`; fields, defaults, decorators, base classes and class keywords are
  untouched; the opener's line holds the marker comment.
- Shapes of function: a multi-line body; a one-line `def f(): return 1`; a
  docstring-only body; `async def`; a method with a nested function (the
  nested one disappears with the body); a decorated `@classmethod` /
  `@property` / `@field_validator`; non-ASCII text before a body on the same
  line.
- The line count of the stub equals the line count through the block's
  closer (nothing after the block is emitted).
- CLI, in `tmp_path`: `main([root])` writes `card.pyi` beside each `.pjx`
  with a block and none for one without; a second run rewrites nothing
  (mtimes unchanged).
- A hand-written `card.pyi` (no marker) beside a block is not overwritten:
  exit code 2 and a message.
- A marked stub whose `.pjx` was deleted, or lost its block, is removed.
- `--check`: writes nothing; exit 0 when fresh; exit 1 and one line per
  problem for a stale stub, a missing stub, an orphaned stub, and a
  `card.py` or `card/` beside a block.
- A block whose Python does not parse: reported with file and line, exit 1,
  other files still processed.
- A block that would write a sentinel file if run: the sentinel does not
  exist after `main`.
- `python -m pyjinhx.stubgen --help` runs (subprocess).

Implement: parse the padded source with `ast`; for each function at module
or class level, replace the source span from its first body statement to its
end with `...`, working bottom-up on the text so earlier positions stay
valid (`col_offset` is in UTF-8 bytes). Plain `argparse`, plain functions.
`.gitignore` is never touched. Why Opus: the in-place edit has to survive
every way a body can be written, and the output is what type-checkers trust.

Manual check, recorded in the task's last commit message: in a scratch
directory, a package with one `.pjx`-hosted class and one `.py` consumer;
run stubgen; `uvx basedpyright` resolves the import and reports the
consumer's deliberate wrong-argument error. Note the pyright setting needed.

## Task 7 — manifest and grammar data file (Opus)

Spec "Facts for editors". Files: `pyjinhx/manifest.py` (new),
`pyjinhx/block_grammar.json` (new, shipped in the wheel: check the hatch
include rules), `pyjinhx/sfc.py` (a small reader for the span of a class's
`template` literal, if `_templates_in` does not already give it),
`pyjinhx/props_header.py` only if the header's signature parse has to be
split from name resolution, `tests/pyjinhx/test_manifest.py` (new),
`tests/pyjinhx/test_block_grammar_corpus.py`.

Tests first:

- One fixture tree in `tmp_path` with a component of each kind. The manifest
  lists four components with `kind` `template`, `pjx-python`, `py-template`
  and `split`, the tags, the paths, and `class.module` from
  `module_name_for`.
- `pjx-python`: block line ranges equal `python_block`'s; `class.line` and
  `column`; `bases` as written; `props` with `annotation` and `default` as
  source text, `required`, `literal_values` for `Literal["a", "b"]`, `slot`
  for `Slot` / `Slot | None` / `list[Slot]`, `children` for `Children`;
  `members` with kinds `property`, `method`, `classmethod`; `stub` is the
  adjacent path when it exists, else null.
- `template`: props from the header, including a dotted type and a dotted
  default, **without importing them** (the dotted module does not exist and
  the manifest still succeeds; `sys.modules` gains nothing).
- `py-template`: the literal's span; two components in one module are two
  entries.
- `split`: `document.path` is the sibling `.pjx`.
- A subclass with no template of its own is not listed (pin the documented
  static limit).
- Columns are UTF-16 code units: a prop declared after a non-BMP character
  on its line reports the right column.
- Diagnostics, one test each, with `code`, `line`, `severity`: each grammar
  error code from task 1; a Python syntax error in a block; `def` with
  `python`; no class named for the file; no markup; a shadowing `card.py`;
  a non-literal `template`; a missing stub; a stale stub. A file with a
  diagnostic still gets its component entry when one can be built.
- `--stdin --filename app/ui/card.pjx` describes the piped text, not the
  file on disk (which may not exist), and reports no stub diagnostics.
- A block that would write a sentinel if run: not run.
- `--grammar` prints `block_grammar.json`; its `version` equals the
  manifest's `grammar_version`; the keywords in it equal the ones the
  scanners accept (assert against the constants, so adding a keyword without
  touching the file fails).
- Output is deterministic: components sorted by path then line; the same
  tree gives the same bytes.

Implement with `ast` only. Do not call `parse_props_header` for the header:
it resolves names and may import; parse the signature text the same way it
does and stop there (share that one step if it is a clean split, otherwise
keep a six-line copy and say why in a comment). The "is this class a
component" rule in a `.py` file is the spec's: it assigns `template`, or a
`<snake>.pjx` sits beside the module. Why Opus: this JSON is a public
contract for another repository; its shape must be right the first time.

## Task 8 — fold script: `pyblock` (Sonnet)

Spec "Migration tooling". Files: `scripts/fold_components.py`,
`tests/test_fold_script.py`.

Tests first (fixtures in `tmp_path`; run it, then import and render the
result and compare with the render from before):

- `card.py` + `card.pjx` → one `card.pjx` whose `python` block body is the
  module's source byte for byte and whose remaining text is the old
  document; `card.py` is gone; the render is unchanged; a sibling `card.css`
  still ships.
- A module with imports, a module docstring, `from __future__ import
  annotations`, a helper function and a relative import folds and imports.
- A module with a second component class that has its own `.pjx`: folded,
  and the report says that class keeps its file.
- Refused, each with its reason and nothing written: source containing `#}`
  (the line is named); no class snaking to the stem; `__init__.py`; the
  class's template is inherited or missing; the class assigns an inline
  `template`; the `.pjx` already has a `python` block; the `.pjx` has a
  `{#def#}` header.
- `--root`: every line under the root that names `card.py` is reported
  (reuse `references`).
- Without `--write` nothing changes. A second `--write` run is a no-op.
- The summary prints the two reminders (root `__init__.py` needs
  `import pyjinhx`; run `python -m pyjinhx.stubgen`).

Implement as one more `Plan`-returning function beside `fold_template`,
wired into `main` like the others. After composing the new text, check
`sfc.python_block` gives back the module source before planning the write.

## Task 9 — user docs, changelog, ADRs (Sonnet)

Files: `docs/guide/components.md` (extend the existing shapes section),
a reference page for the commands (`docs/reference/` — follow how existing
pages are listed in `mkdocs.yml`), `docs/migration.md`, `CHANGELOG.md`,
`docs/reference/public-api.md` if the layout tests require it,
`docs/decisions/0009-a-component-is-a-pjx-document.md`,
`docs/decisions/index.md` (title unchanged, no edit expected),
`docs/superpowers/rebuild/adr/0015-…md` (status → Accepted),
`docs/superpowers/rebuild/adr/README.md` (the 0015 row exists; fix wording).

Content:

- The four shapes with one example each and the P-versus-C table from the
  spec, including the rule of thumb.
- Shape P: the grammar rules; binding by name; what the block may hold; the
  refusals; `import pyjinhx` in the root `__init__.py`; what works and what
  does not (the spec's table).
- Hot reload: the two-row table, the warning, the two uvicorn setups.
- Stubs: the commands, the `.gitignore` line, the pyright setting, CI.
- The commands reference: `pyjinhx.stubgen`, `pyjinhx.manifest` (the JSON
  schema, field by field, and the static-mode limits), `pyjinhx.sfc`
  (extraction and the ruff loop), the grammar file and the corpus, and the
  exact `template = …` forms shape C recognises.
- Tooling gaps table. Security paragraph.
- Migration: v0.x files (remove the space; the class must be named for the
  file); `fold_components.py pyblock`; `pkgutil.walk_packages` and
  `rglob("*.py")` registries do not see `.pjx` modules, `setup()` does.
- Import-hook limits to state (from the Task 2 review): `.pjx` modules are
  not listed by `pkgutil.iter_modules` (discovery globs for them); zip and
  frozen `sys.path` entries never match; coverage.py does not measure `.pjx`
  blocks; `python -m pkg.card` runs through runpy without the stem-class
  check; a `pkg/card/` directory shadows `pkg/card.pjx` (setup refuses it);
  one `.pjx` imported under a second module name is refused.
- Subclasses (from the Task 10 review): `setup()` imports only documents that
  hold a `{#python` block. A plain `.py` subclass of a `.pjx` document's class
  (`class TaskNameField(NameField)` in `todo_name_fields.py`) is registered
  only if something imports it: re-export it from the package's
  `__init__.py`, or import it where the app starts. The parity fixture does
  the former and a test pins the miss without it.
- Discovery notes (from the Task 4 review): a column-0 `{#python` line makes a
  file a document wherever it sits, including an example in a `<pre>`; indent
  the example or write it inside `{% raw %}`. An indented `{#python` stays a
  plain comment. Eager discovery imports every block at `setup()`, so call
  `setup()` after the names your blocks import exist. A block and a module
  that import each other across threads, one through `component_for_tag`,
  can raise `_DeadlockError`; keep that cycle out of the blocks' imports.

Proposed revision of the public ADR (it is unreleased, so it is edited in
place; see open question 1):

```diff
--- a/docs/decisions/0009-a-component-is-a-pjx-document.md
+++ b/docs/decisions/0009-a-component-is-a-pjx-document.md
@@
-**Status:** Accepted, 2026-11-25. Unreleased. Condensed from the rebuild ADR
-0014 (`docs/superpowers/rebuild/adr/`), which supersedes the rebuild's ADR 0008
-(drop `{# python #}` single-file components).
+**Status:** Accepted, 2026-11-25; revised 2026-11-26. Unreleased. Condensed
+from the rebuild ADRs 0014 and 0015 (`docs/superpowers/rebuild/adr/`), which
+together supersede the rebuild's ADR 0008 (drop `{# python #}` single-file
+components).
@@
 v0.x had single-file components, a `{# python #}` block inside a `.pjx`. They were
 dropped because they needed pyjinhx to extract and exec Python from a template
-file, which broke type-checking, import semantics and tracebacks. That objection
-is to a Python-in-template container. It does not apply to a template inside a
-Python file.
+file, which broke type-checking, import semantics and tracebacks. A template
+inside a Python file avoids all of that, and is offered. It also leaves the
+markup as a string no template tooling can read. An editor extension that owns
+the whole `.pjx` file (pjx-ls) can do better than either half alone, so the
+block returns, rebuilt on Python's import protocol, beside the Python-hosted
+form.
@@
 One model: **a component is a pjx document, optionally owned by a Python class.**
-A document is markup plus up to three Jinja-comment blocks: `{#def#}` (props),
-`{#css#}` and `{#js#}`. It lives in a `.pjx` file or in the `template` string
-literal of its class, and means the same in both.
+A document is markup plus Jinja-comment blocks: `{#def#}` (props), `{#css#}`,
+`{#js#}` and `{#python#}` (the owning class). It lives in a `.pjx` file or in
+the `template` string literal of its class, and means the same in both.
@@
    pipeline, sibling file first. Template source is read through one function,
    `read_document`, never `template_path.read_text()`.
+5. **A `.pjx` may hold its class.** `{#python` alone on a line opens a block
+   that is the module `app.ui.card` for `app/ui/card.pjx`; `#}` alone on a line
+   closes it. A finder appended to `sys.meta_path` when `pyjinhx` is imported
+   loads it, compiled so its lines are the file's. The markup belongs to the
+   class named for the file. `setup()` imports every such document under
+   `components_root`; `python -m pyjinhx.stubgen` writes a `.pyi` beside each
+   so type-checkers see the class. Never with `{#def#}`, never beside a
+   `card.py`.
 
-The grammar stays closed at three declarative keywords. There is no `{#python#}`
-block.
+The grammar is closed at these four keywords.
 
-Three shapes follow, none new: T (a `.pjx` alone), C (a `.py` holding its
-template), S (`.py` + `.pjx`, optionally with sibling assets, unchanged). A
-project can mix them per component, and `scripts/fold_components.py` makes the
-mechanical moves.
+Four shapes follow: T (a `.pjx` alone), P (a `.pjx` holding its class), C (a
+`.py` holding its template), S (`.py` + `.pjx`, optionally with sibling assets,
+unchanged). P and C are the same component written two ways: P gives the
+markup full editor support and needs stubs and the import hook; C works with
+stock Python tooling and leaves the markup in a string. A project can mix
+shapes per component, and `scripts/fold_components.py` makes the mechanical
+moves.
@@
 ## Consequences
 
-- Nothing is exec-ed by pyjinhx and no import hook is installed. Python tooling
-  sees an ordinary `.py` file.
+- In shapes T, C and S nothing is exec-ed by pyjinhx and Python tooling sees
+  ordinary `.py` files. Shape P adds an import hook, installed by
+  `import pyjinhx` and consulted only for names nothing else found. Importing a
+  `.pjx` runs its block, so a template is trusted code in the plainest sense.
+- Shape P needs generated stubs for type-checking, and `setup()` imports
+  application code. An edited block applies on restart; pyjinhx warns when it
+  sees one and does not reload modules. Linting and coverage of a block are
+  partial.
+- pyjinhx is the source of pjx facts for editors: `python -m pyjinhx.manifest`,
+  a versioned grammar file and a conformance corpus, none of which imports
+  application code.
@@
-- v0.x `{# python #}` files remain unsupported and still migrate by splitting.
+- v0.x `{# python #}` files migrate by removing the space in the opener,
+  provided the class is named for the file.
```

Any docs test that executes snippets must pass.

### Notes for Task 9 docs (stubgen review)

Mention these in the Stubs section of the guide:

- Annotate return types in blocks. A stub keeps no function bodies, so an
  unannotated `def` is `Unknown` for the type-checker.
- Stricter Pyright modes (`strict`, `reportUnusedImport`, ...) flag the
  stub's `...` statements and unused imports. Recommend keeping the stubs
  resolvable but unchecked with Pyright's `ignore` setting (it suppresses
  diagnostics yet still uses the files for resolution; `exclude` would drop
  them from analysis), scoped to the components root:
  `[tool.pyright] ignore = ["app/components/**/*.pyi"]`.
- Imports in a block are not re-exported by its stub: import a name from the
  module that defines it, never through the component's module.
- `__init__` bodies are kept verbatim in the stub (their `self.x = ...`
  lines declare attributes); every other body becomes `...`.
- The generator skips hidden directories, virtualenvs (`pyvenv.cfg`),
  `site-packages`, `dist-packages`, `build`, `dist`, `__pycache__` and
  `node_modules`, and writes no stub for a block that a `.py` module or
  package shadows.

## Task 10 — fourth shape in the parity fixture (Opus)

Purpose: prove shape P is interchangeable with the other three on the same
app. Files: `tests/fixtures/fewer_files/pjx_python/` (new package, mirroring
`split/`'s directory layout), `tests/pyjinhx/test_fewer_files_parity.py`.

The package, one `.pjx` per component of `split/`, each with its class in a
`python` block and its sibling css/js folded into blocks except `Card`'s
deliberate sibling `card.css`:

| Component | Exercises in shape P |
|---|---|
| `Badge`, `Button`, `Card`, `Toolbar`, `StatusDot`, `EmptyState` | fields-only classes; `Literal`, `ExtraAttrs`, `Slot`, `Children`; inline css; sibling css |
| `Money` | validator, property, classmethod factory, module-level helper in the block |
| `NameField` | the parent and one subclass (`ProjectNameField`) in one block; `TaskNameField` in `todo_name_fields.py`, a `.py` subclass of a `.pjx` class |
| `TodoCount`, `TodoRow`, `TodoList` | `ReactiveComponent`, `react=`, `load()`; one `.pjx` block importing another `.pjx` class |
| `TodoPage` | renders everything above; inline js |
| `broken/` | one document with a Python error on a known line of its block, one with a template error on a known line below a block |

Tests (extend the existing ones; `"P"` joins `SHAPES`, and `shape_classes`
imports `.pjx` modules that have a block as well as `.py` modules):

- Every `EVERY_SHAPE` and `CLASS_SHAPES` markup renders byte-identical in P
  and S (same normalisation as today: auto ids only).
- The full page ships the same asset text in the same order in P and S.
- Dirtying the reactive key swaps the same regions in P and S.
- The two `broken/` errors are reported at their lines of the `.pjx` file:
  the Python one in a traceback frame with the source line printed, the
  template one as today.
- A bad prop is refused the same way in P.
- Shape P's package holds no `.py` except `__init__.py` files, `domain`
  imports and the one deliberate subclass module, and no `.pyi`.
- Publishing P through `config`'s registration path (not by handing classes
  to `build_registry`) finds every class from a clean `sys.modules`: nothing
  in the test imports a P module by name first.
- Stubs: copy the P package to `tmp_path`, run `stubgen.main`, then
  `stubgen.main([..., "--check"])` exits 0, and every stub parses.
- Manifest: over the P package, one `pjx-python` component per document and
  no diagnostics; over all four packages, the same set of tags per shape as
  the classes the test imported (minus the documented static limit).

Module hygiene: the P modules are imported under
`tests.fixtures.fewer_files.pjx_python.…`; the autouse fixture that resets
the registry must not need to unload them (classes are imported once per
session, as the other shapes' are).

## Task 11 — consumer trial re-run (Opus)

**The real consumer app's repository is read-only. Nothing is
written, staged, committed or installed there.** Record
`git status --short` in the real app before and after.

The scratch copy is
`<scratch>/trial-copy`
(its own git repo; one commit per step; scripts under `trial/`). If a reboot
cleared it, rebuild it as the first trial report's "Setup" and "Reproduce"
sections describe, and say so in the new report.

1. In the copy, `git switch -c pyblock-trial f485edb`: the state after the
   `assets` fold and its consumer migration, before `template` and
   `declass`. (Never reset the existing branch.) Point the copy's pyjinhx
   dependency at this worktree. Run both test tiers and
   `trial/parity.py snapshot` for the baseline of this branch.
2. Check the app imports pyjinhx before any `.pjx` module could be imported
   (its `main.py` does; tests import `app.…` directly, so the root package
   `__init__.py` gets `import pyjinhx`). Commit that alone.
3. Whole-population dry run of `fold_components.py pyblock` over the 183
   class-keeping modules and the 91 droppable ones (`trial/all_C.paths`,
   `trial/all_B.paths`): converted, refused, reasons grouped.
4. `pyblock --write` on the first trial's `template` sample
   (`trial/template.paths`: 10 reactive + 10 factory modules) and on the 20
   `declass` sample classes (`trial/declass.paths`), so the classes `declass`
   refused, and `NameField` with its six subclasses, take shape P. Commit
   each bucket separately. Do not rewrite any consumer import: they must
   keep working as they are. That is the answer to the first trial's open
   item 3.
5. After each commit: `trial/parity.py check` (byte parity of HTML and
   assets), then `trial/run_suites.sh <label>`.
6. `python -m pyjinhx.stubgen app`, then the app's own type-check command
   (see its `pyproject.toml`) before and after: new errors, and which
   pyright settings were needed. Then `stubgen --check`.
7. `python -m pyjinhx.manifest app`: component counts per kind, diagnostics,
   wall time.
8. `trial/parity.py timing 9`, A/B/A against the branch baseline, to price
   the startup sniff, the extra imports and the missing bytecode cache.
   The app calls `setup()` three times and its own eager registration walks
   `rglob("*.py")`: record whether either matters.
9. Run the app's ruff config over the tree with stubs ignored, and the
   extraction loop over the folded blocks: new findings (the first trial's
   52 × E501 should be gone in this shape).
10. Write `docs/superpowers/specs/2026-11-26-pjx-python-block-trial.md`:
    per bucket — attempted, converted, refused with reasons; tests before
    and after for both tiers; parity verdicts; type-check and lint results;
    timing against the first trial's table; file counts and the projection
    for the whole app in shape P versus shape C; every consumer change that
    was needed; an "open" list.
11. Anything the trial shows to be a pyjinhx bug gets a failing test in
    pyjinhx first, then a fix, as its own commit. A design gap goes into the
    report's "open" list, not into code.

Done when the report exists, the copy's results are recorded, the full gate
is green on the final commit, and the real repository's status is unchanged.
