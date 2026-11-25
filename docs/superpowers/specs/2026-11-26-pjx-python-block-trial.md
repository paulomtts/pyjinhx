# Shape P (`{#python` blocks): trial on a scratch copy of the consumer app

Plan: `docs/superpowers/plans/2026-11-26-pjx-python-block.md`, task 11.
Method and earlier results: `docs/superpowers/specs/2026-11-25-fewer-files-trial.md`.

## Setup

- **The real app was not touched** (proof at the end).
- **Copy.** The first trial's scratch copy of nomica `a77f18fd` (its own git
  repo). A new branch `pyblock-trial` was cut from `f485edb`: the state after
  the `assets` fold and its consumer migration, before `template` and
  `declass`. Its `[tool.uv.sources]` points at this worktree
  (`feat/ff-py-trial`, editable). One commit per step.
- **Sample.** Chosen by script (`trial/select_pyblock.py`), not by hand: audit
  group C (the 183 modules that must keep a class), each bucket sorted by path
  with every n-th taken (n = len // 10), a module taken by an earlier bucket
  skipped. Buckets: `reactive` (72 in the population), `factory` (82),
  `computed` (15), `multi` (modules with more than one class, 42), `family`
  (every module whose class another class under `app/` subclasses: 6). The
  `reactive` and `factory` samples are the first trial's `template` sample. The
  first trial's `declass` sample (B, droppable classes) is folded too, as a
  sixth step.
- **Tests that ran.** The first trial's two tiers: `tests/frontend` (2300,
  Playwright) and `tests/unit` + `tests/integration` (29 617 collected).
  `tests/conformance` needs Postgres and was not run.
- **Parity harness.** `trial/parity.py`, extended with the new buckets. Props
  are built once from the class fields (required only, then all filled),
  pickled and replayed after each step. No whitespace is normalised; only
  `pjx-N` auto ids and asset tokens are.
- **Type-check.** The app has no type-check command. `basedpyright` 1.40.2 in
  `standard` mode over `app/`, with a `pyrightconfig.json` added to the copy.
- **Lint.** The app's own `[tool.ruff]` over the tree, stubs excluded, plus the
  extraction loop from `docs/guide/components.md` over every block.

## Whole-population dry run (`pyblock`, no write)

| Population | Modules | Converted | Refused |
|---|---|---|---|
| C: keep a class | 183 | 183 | 0 |
| B: droppable | 91 | 88 | 3 |
| Total | 274 | 271 | 3 |

The refusals:

- Two quote `{#def#}` in a docstring (`auth_page.py`, `library_table_head.py`).
  The scanner refuses because `#}` would end the block.
- One has no class named for its stem (`model_relation_inspector.py`).

The script also reported 24 references that stay as they are: 3 modules
mention `__file__`, a few files name a folded `.py` in prose, and some sibling
`.pjx` files keep their own file (see "Multi-class modules").

For comparison, `declass` over the same 91 B modules folds 41 and refuses 56.
Shape P takes all but 3, and every one of the 56 refusals is a class that
shape P keeps as Python.

## Results per bucket

All folds wrote with `pyblock --write --root app`. No consumer import was
rewritten.

| Bucket | Population | Sampled | Converted | Refused |
|---|---|---|---|---|
| reactive | 72 | 10 | 10 | 0 |
| factory | 82 | 10 | 10 | 0 |
| computed | 15 | 10 | 10 | 0 |
| multi | 42 | 10 | 10 | 0 |
| family | 6 | 5 ¹ | 5 | 0 |
| B (first trial's `declass` sample) | 91 | 19 ² | 19 | 0 |
| **Total** | | **64** | **64** | **0** |

¹ The sixth module is also in `computed`.
² 20 paths; `name_field.py` is in `family`.

`NameField` and its six subclasses (`NodeNameField`, `ContextNameField`, …)
fold with no import change. The subclasses still do
`from app….name_field.name_field import NameField`, and the import hook
resolves that to `name_field.pjx`. The same holds for `TabbedDetailShell` (3
subclasses), `LeaseNotice` (4), `GraphChangeStrip` (3), `GraphViewToggle` (3)
and `ChipTextField` (2). This answers the first trial's open item 3, the
`agent_claims` import that `declass` broke.

## Parity

Final check against the baseline snapshot of this branch: **0 differences,
0 errors**. 176 renders were attempted (88 components × minimal and full
props); 152 could be built.

| Bucket | Renders | Byte-identical | Equal up to `pjx-N` ids | Not buildable in the baseline |
|---|---|---|---|---|
| reactive | 20 | 16 | 0 | 4 |
| factory | 22 | 3 | 18 | 1 |
| computed | 18 | 2 | 12 | 4 |
| multi | 24 | 2 | 16 | 6 |
| family | 12 | 0 | 11 | 1 |
| B sample (b_easy + b_hard) | 40 | 11 | 27 | 2 |

The "equal up to ids" renders are explained by two things: the auto-id counter
is process-wide, and the check process starts it at a different value from the
snapshot process (`pjx-877` against `pjx-222`); and `TowerListener`'s random
`tab=` id. With ids replaced, 110 of the 111 such renders are identical, the
111th differs only in the `tab=` id, and all 111 have identical CSS and JS
assets (text and order). The reactive renders run against a stub
load context, so they cover the template and assets but not the data paths.

Subclasses of the family bases were not rendered by the harness. They were
imported and rendered by the test suites below.

## Tests before and after

Unit + integration (`failed` / `errors` / `passed`), each row cumulative:

| Step | Failed | Errors | Passed |
|---|---|---|---|
| Baseline of the branch (`f485edb`, new pyjinhx) | 32 | 10 | 29 585 |
| `reactive` | 35 | 10 | 29 575 |
| `factory` | 37 | 10 | 29 567 |
| `computed` | 37 | 10 | 29 563 |
| `multi` | 37 | 10 | 29 554 |
| `family` | 40 | 10 | 29 548 |
| B sample | 41 | 10 | 29 533 |

Frontend (2300): baseline **2300 passed**. After `reactive`, 2298 passed and 2
failed (`test_discard_upload_confirm_cancel_leaves_the_job_untouched`,
`test_in_a_scrolled_drawer_the_card_sits_under_the_chip`); both passed in 7 s
when run alone. This is the same load-sensitive kind as the first trial's
one flake. After the last fold, **2300 passed**. The frontend tier was run after
`reactive` and after the last step, not after every bucket (about 10 minutes
each).

The 32 + 10 baseline failures are the first trial's: files missing from the
allow-list copy, plus the stylesheet and JS lints that no longer see the
33 folded assets. None belongs to this trial.

**What the 9 new failures are.** No behaviour changed: every one is a test or
lint that scans `.py` files and no longer finds the class.

| Step | Test | Why |
|---|---|---|
| reactive | `test_mutation_key_pairing` | looks for `react=` consumers in `.py` files; two mutation keys now show "no consumer" |
| reactive | `test_dead_import_ratchet` | tests import `….claim_region.claim_region.ClaimRegion`, a module with no `.py` file, so the scan calls it dead |
| reactive | `test_the_scan_sees_every_detail_navbar` | the navbar scan lost one area |
| factory | `test_every_edit_drawer_opts_into_the_unsaved_guard_or_says_why_not` | reads class bodies in `.py` |
| factory | `test_repo_live_surface_declarations_ratchet` | reports `AGENT_RUNS` and `FORM_ROWS` "never mounted" |
| family | `test_files_ship_as_a_triple` × 3 (change strip, view toggle, lease notice) | asserts `<name>.py` exists |
| B sample | `test_repo_tower_publish_subscribe_pairing_ratchet` | same pairing scan |

**43 tests fewer collected** (29 617 → 29 574): `test_component_assets_resolve`
is parametrised from the `.py` modules, so it lost one case for each of 43
folded modules. This is the first trial's open item 4 again, now for classes.

Consumer changes needed: **one line**, `import pyjinhx` at the end of
`app/__init__.py`. Without it a test that imports `app.….card` before
`main` has no import hook. The 9 failing meta tests were left as they are.

## Type-check

`basedpyright`, `standard` mode, `app/`, before and after the folds and
`python -m pyjinhx.stubgen app`:

| | Errors | Warnings |
|---|---|---|
| Before | 2034 | 1 |
| After (64 stubs) | 1975 | 1 |

Comparing by file, rule and message: 64 errors disappeared and 5 appeared.

- **New: 5**, all `"id" overrides a field of the same name but is missing a
  default value`, in `.pyi` stubs (`agent_chip`, `chip_text_field`,
  `context_edit_drawer`, `type_create_drawer`, `member_drawer`). The same 5
  were already reported on the `.py` modules, so they moved, they are not new.
- **Gone: 64** = those 5 plus **59 errors inside method bodies and argument
  expressions of the folded classes** (`reportCallIssue` 26,
  `reportArgumentType` 23, `reportOptionalMemberAccess` 9, …). A stub keeps
  signatures and drops bodies, and pyright does not read a `.pjx`. This is the
  trade-off the design names: in CI only the block's signatures are checked.
- No importer of a folded class got a new error: `from app….name_field
  .name_field import NameField` resolves to the stub next to the `.pjx`.
- Imports of folded classes and unannotated returns: 211 `def`s across the 64
  stubs, **0 without a return annotation**, because the stub copies the source
  signature.
- No pyright setting beyond `standard` was needed.

`python -m pyjinhx.stubgen app`: 64 stubs written in 0.12 s.
`stubgen --check app`: exit 0, before and after the final commit.

## Manifest

`python -m pyjinhx.manifest --sys-path <copy> app`, 0.67 s wall, nothing
imported.

| Kind | Components |
|---|---|
| split (`.py` + `.pjx`) | 221 (+ 75 builtins) |
| template (`.pjx` only) | 93 |
| pjx-python | 68 |
| py-template | 0 |
| **Diagnostics** | **0** |

The first run, before the fix below, gave 97 template and 64 pjx-python. The
4 extra pjx-python entries are the siblings that multi-class modules own
(`AgentChipButton`, `AgentChipDeletedCard`, `TabBarTab`, `ListCardMeta`).

## Lint

- `ruff check app` with the app's config, `*.pyi` excluded: 3 findings
  (2 × UP034, 1 × I001) **before and after**. All 3 were already there.
- The first trial's **52 × E501 are gone**: markup lines stay in the `.pjx`.
- The extraction loop over all 64 blocks: **0 findings**.
- Without the exclusion, ruff reports 301 findings, all in the stubs
  (222 × F401, 39 × UP037, 38 × I001). Stubs need an `extend-exclude` or to be
  git-ignored.

## Timing

`import main` (app import, discovery, eager registration), fresh interpreters,
interleaved A/B/A so drift cancels. The machine was **not idle**: another
project's test run was using four cores for the whole measurement
(load ≈ 3.7), so read the figures as a bound.

| Tree | Runs | Median | Min | Max |
|---|---|---|---|---|
| Before (baseline tree) | 14 | 3.680 s | 3.553 | 7.427 |
| After (64 folds) | 13 | 3.859 s | 3.736 | 4.543 |

About **+0.18 s (+5 %)**, on both the median and the minimum, against the first
trial's +60 ms (+2 %) for 64 folds. Two earlier attempts, one of them while the
suite was running, were discarded: they differed by more than the effect.

Where it goes, from one `cProfile` run of `import main` after the folds
(profiler overhead included, so only the proportions mean anything):

- `build_registry` runs 4 times (the app calls `setup()` three times and
  `import_document` adds one pass); `walk_templates` is called 7700 times,
  0.54 s cumulative.
- The startup sniff (`sfc.python_block` 754 calls, `sfc.comments` 2552 calls)
  costs about 0.1 s.
- 56 `import_document` calls and 64 block executions. A block has no bytecode
  cache, so it compiles on every start (`compile` 5726 calls, 0.07 s).
- The app's own eager registration walks `rglob("*.py")` and imports each
  file (`main.py:351`). It does not see `.pjx` documents, and does not need to:
  the first `setup()` imports every block document before it runs. It did not
  cause a miss. Its "phase 1" is now redundant for the 64 folded modules.

The first trial's 34 `Duplicate component tag` warnings are gone on this
pyjinhx (0 on `import main`, before and after).

## File counts

UI tree (`app/adapters/web/ui`), `.pjx` + `.py` + `.css` + `.js`, the whole app
projected by running each shape on a scratch copy of the baseline tree (all
268 assets folded in every row after the first):

| Shape mix | .pjx | .py | .css/.js | Total | Stubs |
|---|---|---|---|---|---|
| As first audited | 382 | 448 | 275 | 1105 | |
| Split everywhere, assets folded | 382 | 448 | 7 | 837 | |
| **P** for all 271 foldable modules | 382 | 177 | 7 | **566** | 271 `.pyi` |
| **C** (template into the `.py`) for all C and B | 95 | 448 | 7 | **550** | |
| **T** for the 41 B modules `declass` takes, **P** for the rest | 382 | 175 | 7 | **564** | 232 `.pyi` |
| **T** for the 41, **C** for the rest | 136 | 407 | 7 | **550** | |

`assets` folds 235 more assets (268 in all). `template` folds 246 templates in
the C and B modules. The 173 `.py` files that are not components stay in every
row.

- P and C remove about the same number of files (271 against 287). C leaves
  the classes in `.py`, so it can be type-checked, linted and covered as
  Python; P leaves markup and class in one file but adds a stub per document.
- T on top of P saves 2 files (a `.py` is gone either way), and removes 39
  stubs, because a header component needs none.
- The sample alone (64 modules): 64 `.py` files removed, 64 `.pyi` added.

## Multi-class modules

A module with several classes (`agent_chip.py` holds `AgentChipButton`,
`AgentChipDeletedCard` and `AgentChip`) folds into the document named for the
stem, and the other classes keep their own sibling `.pjx` for markup. That
works at run time: each sibling is bound, strict and rendered.

## Bugs fixed in pyjinhx, each with a failing test first

1. **`32c25e4b` — `fix(manifest): a class in a block owns the sibling document
   named for it`.** The manifest listed `agent_chip_button.pjx` as a classless
   template (no class, not strict) although the block defines `AgentChipButton`
   and the runtime binds the two. It also depended on document order. The fix
   claims the sibling for the block's class and describes blocks first.
   Test: `test_a_class_in_a_block_owns_the_sibling_document_named_for_it`
   (with a sibling that sorts before and one that sorts after the block).

The gate on that commit: `ruff format` and `ruff check` clean; `pytest -q`
**6267 passed, 1 skipped, 4 xfailed**; `basedpyright` 0 errors on
`pyjinhx/manifest.py`.

## Open

1. **Tooling that scans `.py` loses coverage silently, for classes this time.**
   9 meta tests fail and 43 parametrised cases disappear (see "Tests"). Every
   consumer lint that reads class bodies or module files needs to read blocks
   (`pyjinhx.sfc.python_source` is the only helper, and it is internal).
   Suggestion: make `python_source` public, or add a small public
   `iter_python_modules(root)` that yields `.py` and block sources alike.
2. **The type-check hole.** In CI, 59 errors in method bodies of 64 folded
   classes are no longer seen; only the editor checks a block's body. A
   `python -m pyjinhx.stubgen --check-bodies` that extracts blocks to a
   temporary tree and runs the checker would close it; the docs only offer
   extraction for ruff.
3. **Stubs trip the consumer's own ruff** (301 findings in 64 files). The docs
   should say to exclude `*.pyi` beside a `.pjx`, or stubgen should write a
   `# ruff: noqa` header.
4. **Docstrings that quote `{#def#}`** make a module unfoldable (2 of 274).
   The refusal is clear, but this is a common thing to write in a docstring of
   a component. Either the scanner accepts `#}` inside a triple-quoted string
   it can see, or the fold script rewrites the text (`"{#def#" "}"` is not
   readable in prose).
5. **The `id` override error moves to the stub** (5 classes). `id: str` without
   a default is what the source says, so the stub repeats it; pyright wants a
   default. Not a regression, but stubgen could emit `id: str = ...`.
6. **The startup cost is real and not tiny:** +0.18 s for 64 blocks, about
   3 ms per block, with `setup()` running four times and no bytecode cache for
   blocks. Two cheap fixes to try: cache the sniff result per path and mtime
   across the repeated `build_registry` passes, and write a `.pyc` for a
   block's compiled code.
7. **A multi-class module leaves sibling `.pjx` files** (4 in the sample; the
   whole-population dry run lists more, for example `ListShellGrid`), so shape P does not reach one file for those. The class lives in
   one document and its markup in another, which a reader has to learn.
8. **A subclass in a plain `.py` is not imported by `setup()`** (a documented
   limit). It was not a problem here, because the app imports the subclasses
   itself, but it is the failure the first trial hit with `declass`.
9. **The harness does not render the subclasses** of the family bases. The
   test suites cover them (all passed), but a parity check for them is
   missing.
10. **Frontend tier was run at two points**, not after every bucket; the unit and
    integration tier was run after every bucket. The only frontend failures
    were two load-sensitive tests that pass alone.

## Reproduce

In the copy (`…/scratchpad/nomica-trial`, branch `pyblock-trial`):

```
.venv/bin/python trial/select_pyblock.py > trial/pyblock_sample.json
.venv/bin/python trial/parity.py snapshot trial/parity/py-baseline
trial/fold_step.sh reactive        # also factory, computed, multi, family, declass
.venv/bin/python trial/parity.py check trial/parity/py-baseline trial/parity/after-reactive
trial/suites.sh reactive           # both tiers; trial/ui.sh <label> for the unit tier only
.venv/bin/python -m pyjinhx.stubgen app && .venv/bin/python -m pyjinhx.stubgen --check app
uvx basedpyright --outputjson      # pyrightconfig.json in the copy
.venv/bin/python -m pyjinhx.manifest --sys-path . app
.venv/bin/python trial/lint_blocks.py app
```

## The real repository, untouched

`git -C /home/mtts/Code/nomica status --short`, before the trial and after it
(identical; HEAD `a77f18fd7c1585704440d33dfe6ccbf2bf79db10` at both points):

```
?? .claude/ledger/
?? .claude/plans/
?? .claude/smoke.lock
?? .codex/
?? docs/artifacts/
?? tmp/
```
