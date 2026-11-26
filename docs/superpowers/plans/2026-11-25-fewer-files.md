# Fewer files per component — implementation plan

Spec: `docs/superpowers/specs/2026-11-25-fewer-files-design.md`.
ADR draft: `docs/superpowers/rebuild/adr/0014-a-component-is-a-pjx-document.md`.
Shape C background: `docs/superpowers/specs/2026-11-25-sfc-v2-candidates.md`.

One PR, one branch: **`feat/fewer-files`**, created from
`feat/inline-css-js-blocks` (front 2, already built) with `feat/sfc-v2`
merged in (these documents, `pyjinhx/sfc.py`, and a failing acceptance test).

## Ground rules for every task

- Strict TDD: write the listed tests first, watch them fail for the stated
  reason, then implement. One granular commit per green step.
- Small, human-looking code. No new abstraction unless two callers exist.
  Docstrings say what; comments say why; no PR or issue numbers in code.
- A new module, or a new import between pyjinhx modules, must be declared in
  `tests/pyjinhx/test_import_graph.py` (`ALLOWED_INTERNAL_IMPORTS`) in the
  same commit.
- Gate before a task is done, from the repo root:
  `uv run ruff format` · `uv run ruff check` · `uv run pytest -q` (about five
  minutes; run the task's own test files first) · `uvx basedpyright`.
- Do not push, open a PR, or touch `master`.

## Order and dependencies

```
0 ─┬─ 1 ── 2 ── 3 ──────────┐
   ├─ 4 ── 5 ───────────────┤
   └─ 6 ── 7 ───────────────┼─ 8 ── 9 ── 10 ── 11
                            │
```

Tasks 1–3 (header), 4–5 (blocks and registration) and 6–7 (shape C) are
three independent chains after task 0 and can be worked in parallel worktrees.
Within a chain the order is fixed: the tasks edit the same files.

| # | Task | Front | Model |
|---|---|---|---|
| 0 | Combined branch | — | Sonnet |
| 1 | Header vocabulary | 1 | Sonnet |
| 2 | Mutable defaults pinned; required `id` | 1 | Sonnet |
| 3 | Dotted names in headers | 1 | Opus |
| 4 | Block grammar hardening | 2 | Sonnet |
| 5 | Header-only templates answer their tags | 1 | Opus |
| 6 | Inline template resolution and loading | 3 | Opus |
| 7 | One document reader; blocks in shape C | 2+3 | Opus |
| 8 | Fold script | all | Sonnet |
| 9 | User docs, changelog, ADR index | all | Sonnet |
| 10 | Three-shape fixture app | all | Opus |
| 11 | Trial on a scratch copy of the consumer app | all | Opus |

---

## Task 0 — combined branch (Sonnet)

1. `git switch -c feat/fewer-files feat/inline-css-js-blocks`
2. `git merge feat/sfc-v2`. Expect one conflict, in
   `tests/pyjinhx/test_import_graph.py`: both sides add table entries. Keep
   both (`template_blocks` and `sfc`; `session` allows `pyjinhx.sfc`).
3. `tests/pyjinhx/test_sfc_component.py` fails at collection: pydantic
   rejects the unannotated `template` while the module is being imported, so
   a skip marker cannot help. Rename it to
   `tests/pyjinhx/sfc_component_acceptance.py.txt` in this task and restore
   the name in task 6.
4. Run the full gate; everything else must be green before any task starts.

## Task 1 — header vocabulary (Sonnet)

Spec §1a. Files: `pyjinhx/props_header.py`,
`tests/pyjinhx/test_props_header_parse.py`,
`tests/pyjinhx/test_props_header_build.py`.

Tests first (parse level, then one build-and-validate each):

- `tone: Literal["info", "warn"] = "info"` → `typing.Literal["info", "warn"]`;
  building the class and passing `tone="bad"` raises `ValidationError`.
- `Literal[SOME_NAME]` → `ValueError` naming the prop (members must be
  literals).
- `items: list[str] = []` → `list[str]`; `by_id: dict[str, int] = {}` →
  `dict[str, int]`; `rows: list[Slot] = []` keeps the slot marker reachable
  (the field is in `descriptor.slot_fields` — check
  `_is_component_typed_annotation` / `_is_slot_field`; if a `list[Slot]` is
  not detected as a slot today, do not widen slot detection here: drop this
  case and note it in the PR description).
- `size: str | int = 1` → a real union (currently `Any`); `"x"` and `2`
  validate, `[]` does not.
- `attrs: ExtraAttrs = {}` and `title: AttrValue = ""` resolve to pyjinhx's
  types; `attrs={'a"b': "x"}` fails validation.
- An unknown bare name still warns once and falls back to `Any` (existing
  test must keep passing unchanged).

Implement by extending `_resolve_annotation` only: a `Subscript` branch for
`Literal` / `list` / `dict`, a real-union return in the `BitOr` branch, and
two names added where `Slot` / `Children` are registered.

## Task 2 — mutable defaults pinned; required `id` (Sonnet)

Spec §1b, §1d. Files: `pyjinhx/props_header.py`,
`tests/pyjinhx/test_props_header_build.py`,
`tests/pyjinhx/test_classless_factory.py`.

Tests first:

- Two instances built from `{#def items: list = [], opts: dict = {} #}` do
  not share `items` or `opts` (this passes today — it is a pin, commit it
  alone as `test:`).
- `{#def id: str, title: str #}`: the built class has `auto_id is False`;
  constructing without `id` raises; with `id="x"` the instance has
  `id == "x"`; `id` is not duplicated in `model_fields` beyond the base field.
- `{#def id: int #}` and `{#def id: str = "fixed" #}` each raise `ValueError`
  whose message says `id` may only be declared as a required `str`.
- A header without `id` still auto-generates ids.

Implement in `build_component_class`: pull an `id` entry out of `fields`
before `create_model`, validate it, and set `cls.auto_id = False` after
creation (same post-creation assignment `_pjx_classless` uses, for the same
reason).

## Task 3 — dotted names in headers (Opus)

Spec §1c. Files: `pyjinhx/props_header.py`,
`tests/pyjinhx/test_props_header_parse.py`,
`tests/pyjinhx/test_props_header_build.py`, plus a tiny helper module for the
tests to import from, `tests/pyjinhx/header_names.py` (a constant, an enum, a
zero-argument function).

Tests first:

- Type: `when: datetime.datetime` → `datetime.datetime`;
  `tone: tests.pyjinhx.header_names.Tone` → that enum, and `tone="warn"`
  coerces.
- Type inside a generic and a union: `list[uuid.UUID]`, `uuid.UUID | None`.
- Constant default: `size: int = tests.pyjinhx.header_names.PAGE_SIZE` →
  default equals the constant.
- Factory default: `at: datetime.datetime = datetime.datetime.now()` → two
  instances built a moment apart can differ; the field's
  `default_factory is datetime.datetime.now`.
- A dotted path that does not import → `ValueError` naming the prop and the
  path, raised from the original `ImportError` / `AttributeError`.
- Still rejected, with a message listing the three allowed forms (literal,
  dotted name, dotted name with `()`): a bare name default, a call with
  arguments, an expression (`a.B * 2`), a lambda.
- Parsing a header imports nothing it does not reference (assert a sentinel
  module is absent from `sys.modules` after parsing a header that does not
  name it).

Implementation notes: one helper that turns an `ast.Attribute` chain into
its dotted text (or `None` if it is not a pure chain) and one call to
`pkgutil.resolve_name`. The parser's return type today is
`(name, annotation, default)` with `...` for required; a factory needs a
fourth state — carry it as `pydantic.Field(default_factory=…)` in the
default position, which `create_model` already accepts, so
`build_component_class` does not change. Why Opus: the error taxonomy and
keeping `parse_props_header`'s contract stable for its other callers
(`classless.component`, `template_has_props_header`).

## Task 4 — block grammar hardening (Sonnet)

Spec "Block grammar, stated once". Files: `pyjinhx/template_blocks.py`,
`pyjinhx/props_header.py`, `tests/pyjinhx/test_template_blocks.py`,
`tests/pyjinhx/test_props_header_parse.py`.

Tests first:

- A `{#css … #}` block above `{#def title: str #}`: `parse_props_header`
  still returns the `title` field (fails today — returns `None`).
- `{#def … #}` in the middle or at the end of a document is found.
- Two `{#def … #}` blocks → `TemplateSyntaxError` with the second one's line.
- Legacy `{# def title: str #}` (spaced) in first position still parses; the
  same text *not* in first position is prose and yields `None`.
- A `{#js … #}` body containing `#}`: scanning the document raises
  `TemplateSyntaxError` at the line of the stray `#}`, and the message names
  both remedies (split the pair, or use a sibling file).
- A document with no css/js block and a literal `#}` in its markup is left
  alone (the check runs only for documents that carry a css or js block).

Implement: `parse_props_header` finds its signature with
`find_block(source, "def", …)`, falling back to the existing anchored regex
for the spaced form; `inline_assets` checks
`"#}" in _COMMENT_RE.sub("", source)` after it has found at least one block.
`props_header` importing `template_blocks` is a new edge — declare it.

## Task 5 — header-only templates answer their tags (Opus)

Spec §1e. Files: `pyjinhx/discovery.py`, `pyjinhx/classless.py`,
`pyjinhx/rendering.py`, `tests/pyjinhx/test_discovery.py`,
`tests/pyjinhx/test_classless_factory.py`, new
`tests/pyjinhx/test_orphan_tags.py` (render-level).

Tests first:

- Discovery: after `build_registry(dir, [])` over a tree with `note.pjx` and
  no class, a new reader `discovery.get_orphan_template("note")` returns its
  path; a stem a class claimed is not an orphan; `build_registry(None, …)`
  yields none. No file under the tree is opened by the build (patch
  `Path.read_text` to raise).
- Two `note.pjx` in different directories: the first in sorted order is
  recorded and one warning names both paths.
- Render: a parent whose template contains `<Note title="hi"/>`, with
  `note.pjx` carrying `{#def title: str #}` and **no** `component("Note")`
  call anywhere, renders the note's markup. Afterwards
  `discovery.get_class("note")` returns the built class.
- Same, where `note.pjx` has **no** header: the tag passes through as
  literal markup, exactly as today, and the file is read once across two
  renders (the "not a component" answer is remembered).
- An empty header `{#def #}` counts as a header.
- A tag with no file (`<WebThing/>`) performs no filesystem access.
- A malformed header surfaces its `ValueError` at render, naming the file.
- A class registered for the tag wins over the orphan template.
- `component("Note")` still works for a headerless orphan and returns the
  same class the tag path built for a headed one.
- Concurrency: two threads rendering the same never-built tag end with one
  class (reuse the pattern of the existing `component()` race test).

Implement: `_Registry` gains an `orphans: dict[str, Path]`, assembled and
published in the same locked rebind as the mapping. `classless` gains one
function, `component_for_tag(tag) -> type | None`, sharing `_build_lock` and
the build code with `component()`. `rendering._fill_children` becomes
`get_class(tag) or component_for_tag(tag)`. `rendering → classless` is a new
edge — confirm it creates no cycle and declare it. Leave
`reactive/fanout.py`'s `get_class` calls alone (classless components are
never reactive) and say so in a comment there only if a test shows it
matters. Why Opus: publish atomicity, the lock, the negative cache and the
import graph.

## Task 6 — inline template resolution and loading (Opus)

Spec "Front 3"; candidates doc "How it works". Files:
`pyjinhx/_component.py`, `pyjinhx/descriptor.py`, `pyjinhx/session.py`,
`pyjinhx/rendering.py`, `tests/pyjinhx/test_sfc_component.py` (restore the
file renamed in task 0), `tests/pyjinhx/test_descriptor.py`,
`tests/pyjinhx/test_component_descriptor.py`, `tests/pyjinhx/test_loader.py`.

The acceptance test already exists and already describes the behaviour:
descriptor fields, render, inheritance and override, a full class with
validator / property / classmethod / module helper, tag expansion between
inline components, syntax-error and traceback line numbers pointing into the
`.py` file, the loader contract for `<path>::<Class>`, and reload-on-edit
without re-import. Make it pass, one test at a time, in roughly this order:

1. `BaseComponent.template: ClassVar[str | None] = None` — collection now
   succeeds.
2. `ClassDescriptor.inline_class: str | None = None` (default keeps every
   existing `ClassDescriptor(...)` call valid).
3. `_walk_template`: before the file probe, an ancestor whose own
   `__dict__` holds a `str` under `template` owns the template; the path is
   that ancestor's module file. Add `_defining_module_file` next to
   `_defining_module_dir`.
4. `AbsolutePathLoader.get_source`: split the name on `::`; with a class
   name, return `extract_template(...)` of the file, the `.py` path as
   filename, and the same mtime-based `uptodate`.
5. `render_level`: ask Jinja for `f"{path}::{inline_class}"` when set.

Add to the acceptance file while there:

- A `ReactiveComponent` subclass with `react={…}` and a `load()` classmethod
  renders from its inline template (the 72-reactive case).
- A class with an inline `template` *and* an adjacent `.pjx`: inline wins.
- A subclass with its own adjacent `.pjx` overrides a parent's inline
  template.
- The render-cache key changes when the `.py` file's mtime changes.

Why Opus: `_walk_template` feeds three callers and ADR 0007's probe budget
(if a test counts `is_file` probes, its number must not move; if none does, add one), and the line
mapping is only as good as the loader's filename contract.

## Task 7 — one document reader; blocks in shape C (Opus)

Spec "Reading a document — the one seam". Files: `pyjinhx/sfc.py`,
`pyjinhx/template_blocks.py`, `pyjinhx/_component.py`,
`pyjinhx/props_header.py`, `pyjinhx/session.py`,
`tests/pyjinhx/test_sfc_extract.py`, `tests/pyjinhx/test_template_blocks.py`,
`tests/pyjinhx/test_sfc_component.py`.

Tests first:

- `read_document(path, None)` is the file's text;
  `read_document(py_path, "Chip")` equals `extract_template` of it.
- A shape C class whose `template` holds a `{#css … #}` block: its
  descriptor's `css_paths` has one `InlineAsset`; reading it returns the
  block body; rendering in INLINE mode emits the style once.
- Two components in one module, each with its own `{#css#}`: no "second
  block" error, two distinct assets, each with the right body, named
  `<path>::<Class>#css`.
- A duplicate block inside one inline template raises with the line number
  **in the `.py` file**.
- A shape C class with a sibling `.css` and an inline block ships both,
  sibling first.
- Editing the block in the `.py` on disk changes what the asset reads,
  without re-import.
- A shape C class whose inline template opens with `{#def … #}` gets the
  stale-header warning once.
- `InlineAsset` for an inline class survives `pickle` round-trip (it
  implements `__reduce__`; the render cache may store descriptors).

Implement: add `read_document`; give `inline_assets` and `InlineAsset` an
optional `inline_class`; thread `inline_class` from `_walk_template`'s owner
into `_resolve_class_descriptor`'s calls; switch the four callers listed in
the spec. `sfc.py` must stay stdlib-only. `template_blocks → sfc` is a new
edge. Why Opus: four call sites across the layering, and `InlineAsset` is a
`Path` subclass with identity semantics the asset pipeline depends on.

## Task 8 — fold script (Sonnet)

Spec "Migration tooling". Files: `scripts/fold_components.py`,
`tests/test_fold_script.py` (fixtures built in `tmp_path`).

Tests first, per operation — run it, then import and render the result and
compare with the render from before:

- `assets`: sibling `card.css` folded into `card.pjx` as a `{#css#}` block
  and deleted; rendered markup and emitted style text unchanged. Skipped and
  reported: content containing `#}`; a template that already has the block;
  an asset inherited by a subclass that has its own template. Second run is
  a no-op.
- `template`: `card.pjx` folded into `class Card` as the last statement,
  `template = r"""…"""`, indented with the class body, file deleted; render
  unchanged; the module still passes `ast.parse`. Skipped and reported:
  content containing `"""` (falls back to `r'''`; skipped only if it holds
  both) or ending in a backslash; a class whose template is inherited.
- `declass`: a fields-only class produces a `{#def#}` header at the top of
  its `.pjx` covering each field (using tasks 1–3's forms) and a report
  listing every file that references the class by name; a class with any
  method, validator, class keyword or non-expressible field is reported as
  "needs a class" with the reason. It never deletes a `.py`.
- `--dry-run` writes nothing for all three.

Plain `argparse`, plain functions, text edits located with `ast` line
numbers. No shipped entry point.

## Task 9 — user docs, changelog, ADR index (Sonnet)

Files: `docs/guide/components.md` (the inline-blocks section from front 2 is
already there — extend, do not duplicate), `docs/migration.md`,
`CHANGELOG.md`, `docs/reference/public-api.md` if `template` counts as
public surface (check `tests/test_package_layout.py` and
`tests/pyjinhx/test_docs_api_boundary.py`),
`docs/superpowers/rebuild/adr/README.md` (the 0014 row already exists; make
its wording match the ADR title).

Content: the one-model sentence; the three shapes with one example each;
the "which shape" table; the header reference (vocabulary, `id`, dotted
names); the raw-string rule; the dev-reload caveat; how to run the fold
script. Any docs test that executes snippets must pass.

## Task 10 — three-shape fixture app (Opus)

Purpose: prove the three shapes are interchangeable on components shaped
like the consumer app's. Files: `tests/fixtures/fewer_files/` with three
sibling packages `split/`, `template_only/`, `single_file/`, and
`tests/pyjinhx/test_fewer_files_parity.py`.

The app, written once per shape (only as far as each shape can express it):

| Component | Exercises | S | T | C |
|---|---|---|---|---|
| `Badge` | `Literal` prop, required `id` | ✓ | ✓ | ✓ |
| `Button` | `ExtraAttrs`, `AttrValue`, inline css | ✓ | ✓ | ✓ |
| `Card` | `Slot` header + `Children` body, sibling css **and** inline css | ✓ | ✓ | ✓ |
| `Toolbar` | nested tags (`<Button/>` ×2 inside `<Card>`), `list` default | ✓ | ✓ | ✓ |
| `Money` | validator + property + classmethod factory + module helper | ✓ | — | ✓ |
| `TodoCount` | `ReactiveComponent`, `react=`, `load()` | ✓ | — | ✓ |
| `TodoPage` | renders everything above; inline js | ✓ | — | ✓ |

Tests:

- For each component, the rendered HTML is byte-identical across every
  shape that implements it (normalise only auto-generated ids).
- The emitted asset text for a full `TodoPage` render is identical between S
  and C; the T package's shared subset matches S.
- In the T package no Python module defines or names any component, and no
  test calls `component()` — tags resolve on their own (task 5).
- In the C package each component is exactly one file and the directory
  holds no `.pjx`, `.css` or `.js`, except `Card`'s deliberate sibling css.
- Dirtying the reactive key re-renders `TodoCount` identically in S and C
  (reuse the fan-out test helpers under `tests/pyjinhx/reactive/`).
- A deliberate error on a known line of one C component is reported at that
  line of its `.py` file.

Each package must be importable under a distinct module path so class names
can repeat; registries are rebuilt per shape inside the test (see the
`reset_registry` fixture pattern in `tests/pyjinhx/test_render_children.py`).

## Task 11 — trial on a scratch copy of the consumer app (Opus)

**The real repository at `/home/mtts/Code/nomica` is read-only for this
task. Nothing is written, staged, committed or installed there.**

1. Copy it to a scratch directory outside both repos. The tree is about
   64 GB, almost all of it data, so copy by allow-list rather than
   exclusion: `app/`, `tests/`, `scripts/`, `main.py`, `pyproject.toml`,
   `uv.lock`, and whatever else the frontend tests import — never `var/`,
   `tmp/`, `.venv/`, `.git/`, `node_modules/`. `git init` the copy so each
   step is diffable.
2. In the copy, create its environment and point pyjinhx at the
   `feat/fewer-files` worktree (editable path dependency). Run the copy's
   frontend tests (`tests/frontend`) **before any conversion** and record the
   baseline; pre-existing failures are not this task's to fix.
3. Choose a sample by script, not by hand — deterministic, e.g. sorted paths
   then every *n*-th — of about ten components per bucket: sibling-css only,
   sibling-js only, "B-easy" classes, "B-hard" classes, reactive classes,
   classes with classmethod factories.
4. Run `scripts/fold_components.py` on the sample: `assets` for the asset
   buckets, `declass` for the B buckets, `template` for the reactive and
   factory buckets. Commit each operation separately in the copy.
5. Re-run the same tests after each operation.
6. Write `docs/superpowers/specs/2026-11-25-fewer-files-trial.md` in the
   pyjinhx worktree: per bucket — attempted, converted, skipped with reasons
   (grouped), tests before and after; every header form that was needed and
   missing; every string the fold script could not express; file counts
   before and after for the sample and the projection for the whole app.
7. Anything the trial shows to be a pyjinhx bug gets a failing test in
   pyjinhx first, then a fix, as its own commit. Anything that is a design
   gap goes into the trial report's "open" list, not into code.

Done when the report exists, the copy's test results are recorded, and
`git -C /home/mtts/Code/nomica status` shows the real repository untouched.
