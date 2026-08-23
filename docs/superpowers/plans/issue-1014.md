<!-- task-pipeline: validated -->
<!-- SPEC VERBATIM — docs/superpowers/specs/issue-1014-design.md -->

# Issue #1014 — document `state_hash_exclude` guidance for per-render-random fields

Subtask of story #1010, milestone 18 ("Nested reactive OOB ownership"). Narrows Story 2 of `docs/superpowers/specs/2026-08-23-nested-reactive-oob-preserve-design.md` (lines 128-160) to its single deliverable. Docs-only.

## Problem

`ReactiveComponent.state_hash()` (`pyjinhx/reactive/component.py:78-89`) digests `model_dump(mode="json", exclude=set(exclude))` where `exclude` is the class's `state_hash_exclude` (`component.py:60`, default `frozenset({"id"})`). Every declared field that is not excluded therefore feeds the digest. A field whose value is freshly minted on every render — a `uuid4().hex` trace/request id, a `datetime.now()` timestamp not derived from persisted data — makes that instance's hash never repeat.

The consequence is in `pyjinhx/reactive/fanout.py:189-198`: `_hash_gate_drops(fresh_hash, entry)` returns `fresh_hash == entry.get("hash")`, and is the only thing that stops a re-rendered region whose output is byte-identical to what the client already shows from being swapped again. A never-repeating hash means that gate can never fire for that class, so every parent dirty event blasts an `outerHTML` swap over every nested child region regardless of whether the child's own data moved — which is precisely the race window Story 1 (#1009, `hx-preserve` stamping, a disjoint code path) exists to narrow.

The mechanism to avoid this already exists and is already reachable from user code. Nothing is missing but the guidance. **No new hashing mechanism is to be proposed or built.**

## Scope

Documentation edits only, at the two insertion points already identified:

- `docs/reactivity.md:66-68` — the existing `state_hash()` bullet in the reactive-fields list. Extend it (or add adjacent prose/callout) with the per-render-random-field warning.
- `docs/api/reactive-api.md:56-68` — the `state_hash()` API entry and the `state_hash_exclude` ClassVar block immediately below it. Same warning, API-reference register.

Both locations should carry the guidance; at minimum `docs/reactivity.md` must, with `docs/api/reactive-api.md` cross-referring rather than duplicating at length if that reads better.

### Content the edit must contain

1. **The rule.** Any field whose value is freshly generated on every render must be listed in `state_hash_exclude`.
2. **The named category**, explicitly: trace ids, request ids, and timestamps not derived from persisted data. Named categories, not a vague "ephemeral state" gesture — the existing text already says "ephemeral UI-only state" and that phrasing is what failed to convey this.
3. **The why**, in terms of observable behavior: an unexcluded per-render-random field makes `state_hash()` never repeat for that instance, which silently defeats the OOB hash gate — every parent dirty event then forces an `outerHTML` swap over every nested child region even when that child's data did not change. Silent is the operative word: nothing raises, nothing warns; the only symptom is over-swapping.
4. **The replace-not-merge gotcha.** `state_hash_exclude` is a `ClassVar[frozenset[str]]` whose subclass value *replaces* the base outright — a subclass that writes `state_hash_exclude = frozenset({"trace_id"})` has just un-excluded `id`. Correct form is `frozenset({"id", "trace_id"})`. This is documented on the ClassVar's own docstring (`component.py:61-62`) but not in the published docs, and it is the mistake a reader following this new guidance will most plausibly make.
5. Optionally a minimal example: a user-defined `ReactiveComponent` subclass with a per-render id field and the corresponding `state_hash_exclude`. Must not be a `PJX*` builtin call — `tests/pyjinhx/test_docs_reference_real_fields.py` parses every `PJXFoo(...)` call and `<PJXFoo ...>` tag in `docs/` and asserts each bare-word keyword is a declared field.

### Out of scope

- Any change to `pyjinhx/reactive/component.py`, `pyjinhx/reactive/fanout.py`, or any other source file.
- Any new tests.
- Story 1 (#1009) `hx-preserve` stamping — separate story, disjoint code path. Reference it only as the race window this guidance narrows.
- **Deferred, flag as a follow-up in the PR description, do not build:** a debug-time affordance warning when the same instance's `state_hash()` differs across back-to-back calls with otherwise-identical field values. Deferred because "otherwise identical" needs its own design pass.

## Observable behavior

No runtime behavior changes. The observable deltas are documentary:

- `docs/reactivity.md` and `docs/api/reactive-api.md` name trace/request ids and non-persisted timestamps as fields requiring exclusion, and state the over-swap consequence of omitting them.
- The replace-not-merge semantics of `state_hash_exclude` appear in published docs for the first time.
- `uv run mkdocs build --strict` continues to succeed — no broken links, no malformed markdown, no orphaned anchors introduced.

## Error paths

None at runtime. The failure modes for this change are build/lint-time:

- A broken internal link or anchor (e.g. cross-linking `reactivity.md` ↔ `api/reactive-api.md` with a wrong heading slug) fails `uv run mkdocs build --strict`.
- An example that names a `PJX*` builtin with a field it does not declare fails `tests/pyjinhx/test_docs_reference_real_fields.py`. Use a user-defined subclass in any example to stay clear of this.
- Prose that describes a *new* mechanism rather than the existing `state_hash_exclude` contradicts the milestone design and must be rejected in review.

## Tests

**No new tests.** Per the milestone spec (lines 187-189), Story 2 is a documentation change with no new test surface: the behavior it recommends — "a field in `state_hash_exclude` does not perturb the hash" — is already covered by `tests/pyjinhx/reactive/test_reactive_state_hash.py`, and the `_hash_gate_drops`/fan-out side is covered by `tests/pyjinhx/reactive/test_reactive_fanout.py` and `tests/pyjinhx/reactive/test_fanout_assets.py`. All three are unaffected by a docs-only change.

Tier note, per this repo's placement rule: there is no unit/integration/e2e taxonomy here — `tests/unit/`, `tests/integration/`, and `tests/reactivity/` are dead directories. The rule (stated at `docs/superpowers/plans/2026-08-16-issue-986.md:31` and reinforced at `docs/superpowers/plans/2026-08-16-issue-980.md:28`) is that a test file mirrors the module or feature under test. Were any test needed for this subtask it would land in `tests/pyjinhx/reactive/test_reactive_state_hash.py` (mirroring `state_hash()` in `reactive/component.py`); none is.

The existing doc-lint `tests/pyjinhx/test_docs_reference_real_fields.py` is the acceptance gate that already mirrors `docs/` and is exercised unchanged by this edit.

## Verification

- fullSuite: `uv run pytest tests/pyjinhx/`, `uv run pytest tests/`, `uv run mkdocs build --strict`, `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`, `python -m build`
- typecheck: `uvx "basedpyright==1.39.9" pyjinhx/`
- lint: `ruff format .`, `ruff check .`

`uv run mkdocs build --strict` and `test_docs_reference_real_fields.py` are the two commands that actually exercise this change.

## Conventions

Docstrings explain WHAT, comments explain WHY; no PR or issue references in prose committed to `docs/`. Prefer small, human-looking prose consistent with the surrounding docs voice.

<!-- END SPEC VERBATIM -->

---

# `state_hash_exclude` Per-Render-Field Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document in the published docs that any field regenerated on every render (trace ids, request ids, timestamps not derived from persisted data) must be listed in `ReactiveComponent.state_hash_exclude`, why omitting it silently defeats the OOB hash gate, and that a subclass's `state_hash_exclude` replaces the base set rather than merging with it.

**Architecture:** Docs-only. Two edits: a new `### Fields that change on every render` subsection at the end of the "Make a component reactive" section of `docs/reactivity.md` (plus a one-clause pointer added to the existing `state_hash()` bullet), and a short API-register paragraph under the `state_hash_exclude` code block in `docs/api/reactive-api.md` that cross-links to the new anchor. No source file changes, no new tests; the acceptance gates are `uv run mkdocs build --strict` (anchors/links/markdown) and the existing doc-lint `tests/pyjinhx/test_docs_reference_real_fields.py`.

**Tech Stack:** Markdown, MkDocs Material (`!!!` admonitions available but not required), pytest, `uv`, `ruff`.

**Spec:** `docs/superpowers/specs/issue-1014-design.md` (reproduced verbatim above)

## Global Constraints

- **No source changes.** `pyjinhx/reactive/component.py`, `pyjinhx/reactive/fanout.py` and every other file under `pyjinhx/` stay untouched. Only `docs/reactivity.md` and `docs/api/reactive-api.md` change.
- **No new tests.** Spec, "Tests": Story 2 has no new test surface. `tests/pyjinhx/reactive/test_reactive_state_hash.py` already covers "a field in `state_hash_exclude` does not perturb the hash"; `tests/pyjinhx/reactive/test_reactive_fanout.py` and `tests/pyjinhx/reactive/test_fanout_assets.py` cover the fan-out/`_hash_gate_drops` side. All three must remain unmodified and passing.
- **Do not propose or build any new hashing mechanism.** `state_hash_exclude` already exists and is already reachable from user code; the deliverable is guidance only. Prose describing a *new* mechanism must be rejected in review.
- **No `PJX*` builtin in any example.** `tests/pyjinhx/test_docs_reference_real_fields.py` parses every `PJXFoo(...)` call and `<PJXFoo ...>` tag in `docs/` and asserts each bare-word keyword is a declared field. Examples use a user-defined `ReactiveComponent` subclass.
- **No PR or issue references in prose committed to `docs/`.** Docstrings explain WHAT, comments explain WHY. Do not write "#1009", "#1010", "#1014", "Story 1", or "milestone 18" into any published docs page.
- **Named categories, not "ephemeral state".** The edit must literally name trace ids, request ids, and timestamps not derived from persisted data. The page already says "ephemeral UI-only state" and that phrasing is exactly what failed to convey the rule.
- **Verification commands run one per invocation, never chained with `&&`:** `uv run pytest tests/pyjinhx/`; `uv run pytest tests/`; `uv run mkdocs build --strict`; `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`; `python -m build`; `uvx "basedpyright==1.39.9" pyjinhx/`; `ruff format .`; `ruff check .`.
- **Branch/worktree:** branch `m18/task-1014`, worktree `/home/mtts/Code/libs/pyjinhx/.claude/worktrees/m18/task-1014`, cut fresh from `origin/master`. Assume no other subtask's code is present — in particular `hx-preserve` stamping from #1009 does **not** exist on this branch, so do not document it.

---

## File Structure

- `docs/reactivity.md` — conceptual guide. Owns the full explanation: rule, named categories, why (hash gate → over-swap), replace-not-merge gotcha, worked example. New subsection `### Fields that change on every render` lives at the end of the `## Make a component reactive` section (currently ends at line 76, immediately before `## Making builtins reactive` at line 78). Its slug is `#fields-that-change-on-every-render`.
- `docs/api/reactive-api.md` — API reference register. Owns a compact restatement under the `state_hash_exclude` ClassVar block (lines 66-68) plus a cross-link to the `reactivity.md` anchor. Deliberately shorter — the guide is the canonical prose.

Nothing else is created or modified.

---

## Task 1: Baseline the two doc gates before touching anything

A docs-only change has no failing unit test to write, so the equivalent of RED here is proving the gates are green *before* the edit (so any later failure is provably ours) and proving the guidance is genuinely absent today.

**Files:**
- Modify: none (read-only baseline)
- Test: none created — per the spec, this subtask adds no test surface. The file that *would* have received one, per this repo's mirror-the-module placement rule, is `tests/pyjinhx/reactive/test_reactive_state_hash.py`; it stays unmodified.

**Interfaces:**
- Consumes: nothing.
- Produces: a confirmed-green baseline for `uv run mkdocs build --strict` and `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`, and the confirmed absence of the anchor `fields-that-change-on-every-render` from the docs tree. Tasks 2 and 3 rely on both.

- [ ] **Step 1: Confirm the guidance is absent today (the "RED" observation)**

Run each, one per invocation, from the worktree root:

```bash
grep -rn "trace_id" docs/reactivity.md docs/api/reactive-api.md
```

```bash
grep -rn "fields-that-change-on-every-render" docs/
```

Expected: both print nothing and exit non-zero (exit code 1, "no match"). If either prints a hit, stop — someone has already landed part of this change and the plan needs re-basing.

- [ ] **Step 2: Confirm the doc-lint gate is green before the edit**

Run: `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`
Expected: PASS.

- [ ] **Step 3: Confirm the strict docs build is green before the edit**

Run: `uv run mkdocs build --strict`
Expected: exit 0, no `WARNING`/`ERROR` lines. Any pre-existing warning must be noted now, because `--strict` turns warnings into failures and you need to know which ones you did not cause.

- [ ] **Step 4: Confirm the existing hash tests are green and will stay untouched**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_state_hash.py tests/pyjinhx/reactive/test_reactive_fanout.py tests/pyjinhx/reactive/test_fanout_assets.py -q`
Expected: PASS. These three files must have zero diff at the end of this plan.

- [ ] **Step 5: No commit**

Nothing changed. Do not commit; proceed to Task 2.

---

## Task 2: Add the guidance subsection to `docs/reactivity.md`

**Files:**
- Modify: `docs/reactivity.md:66-68` (extend the existing `state_hash()` bullet with a pointer) and `docs/reactivity.md:76-78` (insert the new subsection between the `data-pjx-reacts` paragraph and the `## Making builtins reactive` heading)
- Test: none — see Task 1's Files note.

**Interfaces:**
- Consumes: the green baseline from Task 1.
- Produces: the heading `### Fields that change on every render` in `docs/reactivity.md`, whose slug `#fields-that-change-on-every-render` Task 3 links to from `docs/api/reactive-api.md`. If you change the heading wording, Task 3's link target must change with it or `--strict` fails.

- [ ] **Step 1: Extend the existing `state_hash()` bullet with a pointer**

In `docs/reactivity.md`, replace lines 66-68 exactly:

```markdown
- `state_hash()` — canonical SHA-256 of sorted JSON from `model_dump(mode="json")`
  with `state_hash_exclude` applied (`id` is excluded by default). Override for custom
  hashing or add fields to `state_hash_exclude` for ephemeral UI-only state.
```

with:

```markdown
- `state_hash()` — canonical SHA-256 of sorted JSON from `model_dump(mode="json")`
  with `state_hash_exclude` applied (`id` is excluded by default). Override for custom
  hashing, or add fields to `state_hash_exclude` for ephemeral UI-only state — see
  [Fields that change on every render](#fields-that-change-on-every-render) for the
  fields that *must* go there.
```

- [ ] **Step 2: Insert the new subsection before `## Making builtins reactive`**

`docs/reactivity.md` currently reads, at lines 75-78:

```markdown
`data-pjx-reacts` is **not** stamped by the framework; see [Loading
indicators](#loading-indicators-in-flight).

## Making builtins reactive
```

Insert the following block between the `data-pjx-reacts` paragraph and the `## Making builtins reactive` heading (i.e. after line 76, keeping one blank line on each side):

````markdown
### Fields that change on every render

A field whose value is minted fresh every time the component is built — a
`uuid4().hex` trace or request id, a `datetime.now()` timestamp that is not read
back from persisted data — has to be named in `state_hash_exclude`:

```python
from uuid import uuid4

from pydantic import Field


class OrderPanel(ReactiveComponent, react={Keys.TODOS}):
    state_hash_exclude = frozenset({"id", "trace_id"})

    total: int = 0
    trace_id: str = Field(default_factory=lambda: uuid4().hex)
```

`state_hash()` digests every field that is not excluded, so an unexcluded
per-render value gives that instance a hash that never repeats. The hash gate —
the check that drops a swap when a region's freshly computed hash equals the one
the client reported — then has nothing to match on and can never fire, so every
dirty event on the parent forces an `outerHTML` swap over every nested child
region even when the child's own data did not move. Nothing raises and nothing
warns; the only symptom is over-swapping.

`state_hash_exclude` is a `ClassVar[frozenset[str]]`, and a subclass's value
**replaces** the inherited set rather than adding to it. Writing
`frozenset({"trace_id"})` un-excludes `id`, which puts a per-render auto id back
into the digest and reintroduces the same never-repeating hash. Always repeat
`"id"`.
````

- [ ] **Step 3: Verify the anchor and the absence of forbidden references**

Run each, one per invocation:

```bash
grep -n "Fields that change on every render" docs/reactivity.md
```

Expected: two hits — the heading and the pointer added to the `state_hash()` bullet.

```bash
grep -nE "#(1009|1010|1014)|Story 1|milestone 18|hx-preserve" docs/reactivity.md
```

Expected: no output, exit 1. Any hit violates the no-issue-references convention (and `hx-preserve` does not exist on this branch).

```bash
grep -n "PJX" docs/reactivity.md
```

Expected: only pre-existing hits in the "Making builtins reactive" section (`PJXBadge`, `pjx_badge.pjx`, `pjx_badge.css`). The new subsection must contribute none.

- [ ] **Step 4: Run the doc-lint gate**

Run: `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`
Expected: PASS. A failure here means the new example named a `PJX*` builtin with a keyword that is not a declared field — rewrite the example around the user-defined `OrderPanel` subclass instead.

- [ ] **Step 5: Run the strict docs build**

Run: `uv run mkdocs build --strict`
Expected: exit 0, no new warnings versus the Task 1 baseline. A warning naming `#fields-that-change-on-every-render` means the heading text and the in-page link disagree — fix the link to match the heading's slug.

- [ ] **Step 6: Commit**

```bash
git add docs/reactivity.md
git commit -m "docs: require state_hash_exclude for per-render fields"
```

---

## Task 3: Mirror the guidance in `docs/api/reactive-api.md`

**Files:**
- Modify: `docs/api/reactive-api.md:56-68` — the `state_hash()` entry and the `state_hash_exclude` ClassVar code block directly beneath it
- Test: none — see Task 1's Files note.

**Interfaces:**
- Consumes: the anchor `#fields-that-change-on-every-render` created in Task 2. This page links to it as `../reactivity.md#fields-that-change-on-every-render` (the page lives one directory down, matching the existing `../reactivity.md#making-builtins-reactive` link at line 38).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Add the API-register guidance under the ClassVar block**

`docs/api/reactive-api.md` currently reads, at lines 56-70:

````markdown
### state_hash()

```python
def state_hash(self) -> str
```

SHA-256 of canonical sorted JSON from `model_dump(mode="json")` with
`state_hash_exclude` applied (`id` excluded by default on `ReactiveComponent`).
Used by OOB swap gating — override for custom hashing.

```python
state_hash_exclude: ClassVar[frozenset[str]] = frozenset({"id"})
```

## PjxKey
````

Insert the following two paragraphs between the `state_hash_exclude` code block and the `## PjxKey` heading (i.e. after line 68, blank line on each side):

```markdown
A subclass's `state_hash_exclude` **replaces** this set rather than adding to it:
`frozenset({"trace_id"})` un-excludes `id`. Write `frozenset({"id", "trace_id"})`.

Any field regenerated on every render belongs in it — trace ids, request ids, and
timestamps not derived from persisted data. Left in the digest, such a field makes
`state_hash()` never repeat for that instance, so the OOB gate can never drop a
redundant swap and every dirty event on a parent re-swaps every nested child
region. See [Fields that change on every
render](../reactivity.md#fields-that-change-on-every-render).
```

- [ ] **Step 2: Verify no forbidden references crept in**

Run: `grep -nE "#(1009|1010|1014)|Story 1|milestone 18|hx-preserve" docs/api/reactive-api.md`
Expected: no output, exit 1.

- [ ] **Step 3: Run the doc-lint gate**

Run: `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`
Expected: PASS.

- [ ] **Step 4: Run the strict docs build — this is what validates the cross-page anchor**

Run: `uv run mkdocs build --strict`
Expected: exit 0. A warning about a link to `reactivity.md#fields-that-change-on-every-render` means Task 2's heading text differs from the slug used here; make them agree.

- [ ] **Step 5: Commit**

```bash
git add docs/api/reactive-api.md
git commit -m "docs: note state_hash_exclude replace semantics in API reference"
```

---

## Task 4: Full verification and PR

**Files:**
- Modify: none (verification only; `git diff origin/master --stat` must show exactly `docs/reactivity.md` and `docs/api/reactive-api.md`, plus this plan and the spec under `docs/superpowers/`)
- Test: none.

**Interfaces:**
- Consumes: the committed edits from Tasks 2 and 3.
- Produces: the PR, including the deferred-follow-up note the spec requires.

- [ ] **Step 1: Confirm the diff is docs-only**

Run: `git diff origin/master --stat`
Expected: only `docs/reactivity.md`, `docs/api/reactive-api.md`, and the `docs/superpowers/` spec + plan files. Any file under `pyjinhx/` or `tests/` in that list violates the spec's out-of-scope list — revert it.

- [ ] **Step 2: Lint format**

Run: `ruff format .`
Expected: "N files left unchanged" — a docs-only change should reformat nothing. If it rewrites a Python file, you touched source; revert.

- [ ] **Step 3: Lint check**

Run: `ruff check .`
Expected: "All checks passed!".

- [ ] **Step 4: Typecheck**

Run: `uvx "basedpyright==1.39.9" pyjinhx/`
Expected: 0 errors (unchanged from the branch point, since `pyjinhx/` was not touched).

- [ ] **Step 5: Package test suite**

Run: `uv run pytest tests/pyjinhx/`
Expected: PASS.

- [ ] **Step 6: Full test suite**

Run: `uv run pytest tests/`
Expected: PASS.

- [ ] **Step 7: Strict docs build**

Run: `uv run mkdocs build --strict`
Expected: exit 0.

- [ ] **Step 8: Doc-lint gate**

Run: `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`
Expected: PASS.

- [ ] **Step 9: Build the distribution**

Run: `python -m build`
Expected: sdist and wheel built, exit 0.

- [ ] **Step 10: Open the PR with the deferred follow-up recorded**

Push the branch and open the PR against the branch this worktree was cut from. The PR description must carry the deferred item — the spec requires it be flagged there and nowhere in `docs/`:

```
Documents the rule that any field regenerated on every render (trace ids,
request ids, timestamps not derived from persisted data) must be listed in
`ReactiveComponent.state_hash_exclude`, why omitting it silently defeats the OOB
hash gate and forces `outerHTML` swaps over unchanged nested children, and that a
subclass's `state_hash_exclude` replaces the base set rather than merging with it.

Docs-only: `docs/reactivity.md` and `docs/api/reactive-api.md`. No source changes,
no new tests — `tests/pyjinhx/reactive/test_reactive_state_hash.py` already covers
the hash-exclusion behaviour and is untouched.

Follow-up (deliberately not built here): a debug-time affordance that warns when
the same instance's `state_hash()` differs across back-to-back calls with
otherwise-identical field values. Deferred because "otherwise identical" needs its
own design pass.
```

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Rule: per-render-generated fields go in `state_hash_exclude` | Task 2 Step 2 (subsection opening sentence), Task 3 Step 1 (second paragraph) |
| Named category: trace ids, request ids, timestamps not derived from persisted data | Task 2 Step 2 (`uuid4().hex` trace/request id, `datetime.now()` not read back from persisted data), Task 3 Step 1 (verbatim list) |
| Why, in observable terms: hash never repeats → gate never fires → `outerHTML` over unchanged nested children, silently | Task 2 Step 2 (second paragraph, ends "the only symptom is over-swapping"), Task 3 Step 1 |
| Replace-not-merge gotcha for the `ClassVar` | Task 2 Step 2 (third paragraph), Task 3 Step 1 (first paragraph) |
| Optional example, user-defined subclass, no `PJX*` | Task 2 Step 2 (`OrderPanel`), guarded by Task 2 Step 3's `grep -n "PJX"` and Step 4's doc-lint run |
| Both insertion points (`docs/reactivity.md:66-68`, `docs/api/reactive-api.md:56-68`) | Task 2 Steps 1-2, Task 3 Step 1 |
| No source changes | Global Constraints; enforced by Task 4 Step 1 |
| No new tests | Global Constraints; Task 1's Files note names `tests/pyjinhx/reactive/test_reactive_state_hash.py` as the file that would have received one; Task 1 Step 4 pins the three existing files green |
| No new hashing mechanism proposed | Global Constraints; all prose describes only the existing `state_hash_exclude` |
| Story 1 / `hx-preserve` stays out | Global Constraints; enforced by the greps in Task 2 Step 3 and Task 3 Step 2 |
| Deferred back-to-back-`state_hash()` warning flagged in the PR description only | Task 4 Step 10 |
| `mkdocs build --strict` stays green | Task 1 Step 3 (baseline), Task 2 Step 5, Task 3 Step 4, Task 4 Step 7 |
| Doc-lint test stays green | Task 1 Step 2, Task 2 Step 4, Task 3 Step 3, Task 4 Step 8 |
| No PR/issue references in `docs/` prose | Global Constraints; Task 2 Step 3 and Task 3 Step 2 greps |

No gaps.

**2. Placeholder scan**

No "TBD", "TODO", "similar to Task N", or "add appropriate handling". Every doc edit is given as the literal replacement text with its surrounding context quoted from the file as it exists at `docs/reactivity.md:66-78` and `docs/api/reactive-api.md:56-70`. Every verification step names one exact command and its expected output.

**3. Type consistency**

The example uses `state_hash_exclude = frozenset({"id", "trace_id"})`, matching the declared `ClassVar[frozenset[str]]` at `pyjinhx/reactive/component.py:60` (annotation omitted in the example, as is normal for a subclass override). `Keys.TODOS` is the member defined earlier on the same page (`docs/reactivity.md:35-36`), not an invented one. `Field(default_factory=...)` is imported in the snippet (`from pydantic import Field`) alongside `from uuid import uuid4`; `ReactiveComponent` is already imported in the page's first example. The anchor string `fields-that-change-on-every-render` is used identically in Task 2 Step 1, Task 2 Step 2's heading (`### Fields that change on every render` → that slug), and Task 3 Step 1's `../reactivity.md#...` link. The relative path `../reactivity.md` matches the existing working link at `docs/api/reactive-api.md:38`.
