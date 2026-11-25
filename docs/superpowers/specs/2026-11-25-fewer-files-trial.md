# Fewer files per component: trial on a scratch copy of the consumer app

Plan: `docs/superpowers/plans/2026-11-25-fewer-files.md`, task 11.
Spec: `docs/superpowers/specs/2026-11-25-fewer-files-design.md`.

## Setup

- **The real app was not touched.** `git status --short` in
  the real app was recorded before the trial and compared after it (see the end).
  Nothing was installed there, and every command ran in the copy.
- **Copy.** Made by allow-list from the app's commit `a77f18fd`: `app/`, `tests/`,
  `scripts/`, `main.py`, `pyproject.toml`, `uv.lock`, `.python-version` and
  `.gitignore`, with no `__pycache__`. The copy is 43 MB, against a 64 GB
  tree. It has its own git repo, so each step below is one commit.
- **pyjinhx.** An editable path dependency on the `feat/ff-trial` worktree.
  The final numbers come from `d86a6d01`, which is `feat/fewer-files`
  (including the 13 review fixes) merged with this trial's two script fixes.
  The `.venv` is symlinked into the uv cache (12 MB).
- **Sample.** Chosen by script (`trial/select_sample.py`), not by hand. It is
  seeded from the earlier audit's buckets (`k.json`: B = 91 droppable
  classes, C = 183 that must keep a class). Each bucket is sorted by path and
  every n-th item is taken, with n = len // 10. The class buckets are chosen
  first, and the asset buckets skip any directory already sampled, so each
  operation touches its own files.
  - `b_easy` is a B class with at most one header gap (36 classes); `b_hard`
    has two or more (55). The audit's own 31/60 split used a rule that was
    not recorded, so this rule is stated here instead.
  - `css_and_js` is an extra bucket: `js_only` has only 3 members in the
    whole app.
- **Tests that can run.** Neither tier needs a DB:
  - `tests/frontend`: Playwright against a fake backend, 2300 tests.
  - `tests/unit` + `tests/integration`: the app's Docker-free gate, 29 644
    tests.
  - `tests/conformance` needs Postgres and was not run.
- **Parity harness** (`trial/parity.py`). It builds props for every sampled
  component from its class fields, twice: required fields only, then every
  field filled. The props are pickled and reused after each fold. Each
  component is rendered at top level in a request scope, with a stub load
  context for reactive components. Each render saves the HTML and the text
  and order of every CSS/JS asset it pulled in. Only these are normalised:
  - auto ids (`pjx-N`);
  - TowerListener's random `tab=` id;
  - asset tokens and URLs.

  **No whitespace is normalised.** With the newline fix (`c7b5c748`) every
  fold must be byte-identical, and every fold was. 114 of the 128 renders
  could be built; the other 14 could not get props, for example because of
  validators or because of context the stub cannot fake.

## Results per bucket

| Bucket | Population | Sampled | Operation | Converted | Refused |
|---|---|---|---|---|---|
| reactive | 72 | 10 modules | `template` | 10 templates | 0 |
| factory | 82 | 10 modules | `template` | 11 templates (`tab_bar.py` holds 2) | 0 |
| b_easy | 36 | 10 | `declass` | 8 | 2: field docstrings (1), required prop after an optional one (1) |
| b_hard | 55 | 10 | `declass` | 2 | 8: field docstrings (3), `Field(min_length=1)` (1), `tuple[...]` annotation (1), subscript default `TRANSLATIONS[...][...]` (1), second class in the module (1), module-level assignment (1) |
| css_only | 141 | 10 | `assets` | 10 css | 0 |
| js_only | 3 | 3 | `assets` | 3 js | 0 |
| css_and_js | 43 | 10 | `assets` | 20 (10 css + 10 js) | 0 |

Render parity after the last fold, by verdict:

| Bucket | Byte-identical | Identical up to ids and asset tokens | Not renderable in the baseline |
|---|---|---|---|
| reactive | 16 | 0 | 4 |
| factory | 3 | 18 | 1 |
| b_easy | 6 | 14 | 0 |
| b_hard | 3 | 15 | 2 |
| css_only | 3 | 17 | 0 |
| js_only | 0 | 3 | 3 |
| css_and_js | 4 | 12 | 4 |

No render differed after any of the three operations. The check
compares asset order and asset text as well as the HTML. One caveat: the
reactive renders run against a stub context, so they cover the template and
assets but not the data paths.

## Tests before and after

Each row is cumulative and builds on the row above it.

| Step | Frontend (2300) | Unit + integration |
|---|---|---|
| Baseline, nothing folded | **2300 passed** | 15 failed, 29 629 passed |
| `assets`, as the script leaves it | 1922 passed, **362 failed, 16 errors** | 203 failed, 10 errors |
| … plus a migration of code that names asset files by path | **2300 passed** ¹ | 33 failed, 10 errors |
| `template` | 2299 passed, 1 flaky ² | 34 failed, 10 errors |
| `declass`, plus imports rewritten to `component("X")` | **2300 passed** | 36 failed, 10 errors; 7 tests fewer collected |

¹ 2246 passed with 8 collection errors in the full run. My path rewriter had
put an import inside a docstring. After fixing that, the file
(`test_graph_inspector.py`) passed 54/54 on its own.

² `test_in_a_scrolled_drawer_the_card_sits_under_the_chip`: a pixel-position
assertion that failed under `-n 8` load. It passed 3/3 alone, and its whole
file passed 65/65. It passed again in the declass run.

What the unit + integration numbers are made of:

- **Baseline (15).** All 15 come from the allow-list copy: `docs/`,
  `CLAUDE.md` and `docker-compose.yml` are missing. None of them is this
  task's to fix.
- **The `assets` fold as written (+188 failures, +10 errors).**
  - 175 come from `NodeConfigDrawer`, which passes `caret_menu.css`,
    `caret_menu.js` and `response_format_fields.css` to `borrow_assets` by
    literal path. Rendering it raises `FileNotFoundError`.
  - The rest are tests that read sibling files.
  - The 362 frontend failures have the same cause (agent builder drawers),
    plus the ontology graph tests, which inject `*_toolbar.css` and
    `ontology_path.css` into the page by file path.
- **The migration commit** (copy only):
  - rewrites 16 path expressions into `InlineAsset(<template>.pjx, "css")`;
  - makes the app's `borrow_assets` keep the object, and classify it by its
    name's tail instead of by `.suffix`;
  - makes the frontend helpers inject `content=path.read_text()` rather than
    `path=str(path)`.
- **After the migration (18 failures + 10 errors above baseline).** Every one
  is a test that reads an asset file by path, or asserts its file name.
  - Token-ratio ceilings (10 errors).
  - Stylesheet and JS lint: `test_graph_stylesheets`, `test_shared_skins`,
    `test_caret_menu_source`, `test_library_doc_discard_hidden`,
    `test_destructive_confirms_typed`.
  - `test_phantom_token_fallbacks`: a custom property defined in a folded
    stylesheet is no longer seen, so `app.css`'s use of it is flagged.
  - `test_overlay_close_mechanism`: JS inside a `.pjx` is now classed as
    "template code".
  - Five integration tests that assert `*.css` names or the
    template/class/stylesheet triple.
- **`template` (+1).** `test_every_base_primitive_is_mounted` scans `.pjx`
  files for `<ElapsedClock` and `<GraphNotices`. Those templates now live
  in `.py` files.
- **`declass` (+2).**
  - `test_route_module_imports_in_a_fresh_interpreter[agent_claims]`, a real
    migration hazard; see the open list.
  - `test_the_shared_module_is_domain_blind`, which reads `composer_bar.py`.
  - The 7 tests no longer collected are `test_component_assets_resolve[X]`,
    which is parametrised over imported `BaseComponent` subclasses. A
    header-only component is not a class until it is first used, so that
    meta test quietly lost coverage of 7 components.

## Header forms that were needed and missing

These come from the whole-population dry run of `declass` over the 97
classes in the 91 B modules. 40 fold. Before this trial's two script fixes
the figure was 29.

| Blocker | Classes | Kind |
|---|---|---|
| Field docstrings (a string under a field) | 15 | design: a header has nowhere to keep them |
| `tuple[...]` and `InstanceOf[...]` annotations | 11 | header vocabulary |
| Module-level helper or constant beside the class | 6 assigns, 3 classes | needs a class (expected) |
| `id` with a fixed default, for example `id: str = "navbar"` | 5 | design (task 2 rejects it on purpose) |
| Type defined in, or not imported into, the same module | 4 | needs a class (expected) |
| Required prop after an optional one | 3 | header grammar: Python signature order |
| Methods | 3 | needs a class (expected) |
| No `.pjx` beside the class | 3 | expected |
| Subscript or expression defaults (`_T['…']`, `TRANSLATIONS[…][…]`) | 2 | header vocabulary |
| `Field(min_length=1)` constraint | 1 | header vocabulary |
| Default naming a name that is not imported | 1 | expected |

## Strings the fold script could not express

None. `template` folded all 193 templates of the 183 C modules in the dry
run, and `assets` folded all 268 sibling assets. The sample's 21 templates
and 33 assets folded with no refusal. The script did hit two side issues:

- The folded modules break the consumer's own lint: **52 × E501** across the
  20 modules, because long `.pjx` lines are now Python lines. `ruff format`
  is happy with them.
- `assets` reports nothing about code that names the deleted file (see the
  open list).

## File counts

| | Before | After |
|---|---|---|
| Sample (files of the sampled stems) | 184 | 121 (−63) |
| UI tree, all `.pjx` / `.py` / `.css` / `.js` | 1105 | 1041 (−64: 33 assets, 21 `.pjx`, 10 `.py`) |

The extra file in the UI-tree total is `tab_bar_tab.pjx`, which folded
along with its module.

**Projection for the whole app**, from the dry runs:

- The 382 `.pjx`, 275 component `.py` and 268 sibling assets (925 files)
  become **424 files**: −268 assets, −193 templates, −40 classes.
- That falls to **about 370 files** if the 57 refused B classes take
  `template` instead.
- Getting there needs the consumer-side migration described under "Tests
  before and after", repeated for every path-coupled asset.

## Import and registry build time

Measured as `import main`, which covers the app import plus discovery and
eager registration. Each figure is the median of 9 fresh interpreters,
taken A/B/A on an idle machine:

| Tree | Median |
|---|---|
| After all three folds | 3.358 s |
| Before (baseline tree) | 3.299 s |
| After all three folds | 3.372 s |

That is about +60 ms (+2 %) for 64 folded files. The noise is ±40 ms.

## Bugs fixed in pyjinhx, each with a failing test first

1. **`4b22a55b` — `fix(scripts): declass writes Field(default_factory=...) as
   a header default`.** The spec says ``Field(default_factory=list)` is just
   `= []` ``, but the script refused it, which blocked 12 classes. Now `dict`
   and `list` become `{}` and `[]`, and any other factory becomes the dotted
   `name()` form.
2. **`9aef1f66` — `fix(scripts): declass writes an object annotation as
   Any`.** This blocked 6 classes.

`feat/fewer-files`' review fix "declass refuses call defaults" conflicted
with fix 1 in `header_default`. Merge `d86a6d01` keeps both behaviours: the
`Field(default_factory=…)` case comes first, and every other call is still
refused. All 48 fold-script tests pass.

The gate on `d86a6d01`:

- `ruff format` and `ruff check` are clean.
- `pytest -q`: 5789 passed, 1 skipped, 1 xfailed, 1 xpassed.
- `uvx basedpyright` reports 0 errors in the files this trial changed. The
  58 errors elsewhere were already there before it.

## Open

1. **`assets` cannot see code that names the sibling file.** In this app:
   - `borrow_assets(…, _CARET_MENU / "caret_menu.css")`;
   - frontend tests inject stylesheets by path;
   - meta lints read `*.css` and `*.js` directly.

   Folding the 33 sample assets broke 362 frontend tests, 16 frontend
   collection errors and 175 integration tests until the consumer was
   migrated. Suggestion: `assets --root` reports, or refuses, an asset whose
   file name appears in a string under the root, the way `declass` reports
   references.
   **Fixed** (`35bc27cb`): `assets --root` reports every line under the root that names the
   folded file, and the summary counts them. It does not refuse.
2. **`InlineAsset` is a `Path` that fails on ordinary `Path` handling.**
   - Its `.suffix` is `.pjx#css`, not `.css`.
   - `Path(inline_asset)` drops how it reads.

   As a result, the app's `borrow_assets` filter **silently dropped**
   `ConfirmTypedModal`'s stylesheet from `MoveDomainModal`, and no test in
   either tier caught it. The trial found it by inspecting the descriptor.
   Options: give `InlineAsset` a `.suffix` of `.css` / `.js`, or document
   that consumers must not re-wrap or classify descriptor paths.
   **Fixed** (`cb888c94`): `InlineAsset.suffix` is `.css`/`.js`,
   `.stem` the template's stem and `.name` `card.css`; `str()` is unchanged.
   `Path(asset)` still loses the inline reading, and the guide says so.
3. **A header-only component has no importable class.** Python that imported
   a declassed class now needs `X = component("X")`, and that only works
   once discovery knows the template directory. `NameField` has 6 subclasses
   (`class NodeNameField(NameField)`). After `declass`, the route module
   `agent_claims` no longer imports in a fresh interpreter (`LookupError: …
   has no directory to search`). The fold script folded `NameField` with no
   warning. Suggestions:
   - `declass` refuses a class that another class under `--root` subclasses;
   - or pyjinhx gives a lazy, importable handle for a header-only component.

   **Fixed** (`32dd4f1c`, first option): `declass` refuses a class that any class under the paths or
   `--root` subclasses, and lists the locations.
4. **Tooling that scans by file extension loses coverage without saying so.**
   - CSS lints and token ratios no longer see folded stylesheets.
   - The overlay ratchet re-classifies JS that now sits in `.pjx` files.
   - The "every primitive is mounted" scan no longer sees templates that
     moved into `.py` files.
   - Meta tests parametrised over `BaseComponent` subclasses skip header-only
     components.

   Each consumer has to retarget its tooling at `read_document` and blocks.
   It is worth a migration note.
5. **Field docstrings** are the largest single blocker for `declass`: 15 of
   the 57 refusals. A header could carry them as `#` comments, which the
   signature parser already ignores, except after the last prop. The design
   needs to decide.
6. **Header vocabulary gaps** found in the app:
   - `tuple[...]` (11 classes; **fixed** in `b23efc8e`, with `tuple[int, ...]`, and `declass` writes it);
   - an `id` with a fixed default (5, rejected on purpose by task 2);
   - required after optional (3; the header uses Python signature order and
     rejects keyword-only `*`);
   - `Field` constraints (still not expressible; the refusal now says so, `b1447449`);
   - subscript defaults.
7. **Line length.** Inline templates put long markup lines into `.py` files:
   52 × E501 against the consumer's `line-length = 100`. Consumers need a
   per-file ignore, or the docs should say so.
8. **A misleading refusal message.** The merged "call defaults" refusal
   explains `Field(min_length=1)` as "called once, when the class is
   defined". It is really a constraint the header cannot express.
   **Fixed** (`b1447449`).
9. **`assets`' subclass check only sees modules under the given paths.**
   The whole-app dry run had no such case, but folding a subset of paths
   could miss a subclass elsewhere.
10. **Pre-existing, unrelated.** 34 `Duplicate component tag 'x' claimed by
    A, A` warnings on every `import main`. They appear the same on `master`
    pyjinhx. The app's eager registration probably offers each class twice.

## Reproduce

In the copy (`<scratch>/trial-copy`; its git log has one commit per
step):

```
.venv/bin/python trial/select_sample.py > trial/sample.json
.venv/bin/python trial/parity.py snapshot trial/parity/baseline      # before any fold
.venv/bin/python <ff-trial>/scripts/fold_components.py assets --write $(cat trial/assets.paths)
.venv/bin/python trial/parity.py check trial/parity/baseline trial/parity/after-assets
trial/run_suites.sh after-assets
.venv/bin/python trial/parity.py timing 9
```

## The real repository, untouched

`git status --short` in the real app, before the trial and after
it (identical; HEAD `a77f18fd` at both points):

```
?? .claude/ledger/
?? .claude/plans/
?? .claude/smoke.lock
?? .codex/
?? docs/artifacts/
?? tmp/
```
