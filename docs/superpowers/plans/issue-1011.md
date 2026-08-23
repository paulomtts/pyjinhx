<!-- task-pipeline: validated -->
# Spec (verbatim)

> The following is the spec this plan implements, copied verbatim from `docs/superpowers/specs/issue-1011-design.md`.

---

# Issue #1011 — declare `ReactiveComponent.retain_across_parent_swaps`

Subtask 1 of 3 under story #1009 (`hx-preserve` retention for disjoint nested reactive regions, fixes #1008), milestone 18 "Nested reactive OOB ownership". Narrows the milestone design at `docs/superpowers/specs/2026-08-23-nested-reactive-oob-preserve-design.md:110-112` to its first slice: the declaration of the opt-out flag, with nothing reading it yet.

## Scope

In scope: one new public ClassVar on `ReactiveComponent` in `pyjinhx/reactive/component.py`, plus unit tests for it.

```python
retain_across_parent_swaps: ClassVar[bool] = True
```

It is placed in the existing ClassVar block in the class body (`pyjinhx/reactive/component.py:52-67`), next to `state_hash_exclude` (line 60), which is its closest sibling in both name and role — a public, subclass-overridable knob, as opposed to the `_pjx_`-prefixed derived facts around it. It carries a short prose docstring immediately below the assignment, matching the convention of every other ClassVar in that block (docstring, not an inline comment), saying what the flag means and that a subclass sets it `False` to opt out of ever being preserved against an ancestor's OOB swap — i.e. to declare itself fully owned by its parent.

Out of scope, and explicitly owned by the sibling subtasks, which are still Backlog:

- Recording nested react-keys during dirty rebuilds — `pyjinhx/reactive/root_attrs.py` and `pyjinhx/reactive/fanout.py` (#1012).
- Reading this flag and splicing `hx-preserve="true"` in `oob_swaps()` — `pyjinhx/reactive/fanout.py` (#1013).

#1011 must not touch `root_attrs.py` or `fanout.py`. No `__init_subclass__` / `__pydantic_init_subclass__` change is needed: unlike `react=(...)` and the cache kwargs, this flag has no consumption path at class-definition time. It is a plain inherited ClassVar that a subclass overrides by reassignment in its body, exactly the mechanism `state_hash_exclude` uses.

## Observable behavior

- `ReactiveComponent.retain_across_parent_swaps` exists and is `True`.
- A subclass that says nothing inherits `True`; the value is visible on both the class and an instance.
- A subclass that assigns `retain_across_parent_swaps = False` reads back `False` on that class and its own subclasses, while `ReactiveComponent` and unrelated sibling subclasses still read `True` — the override is per-class, never a mutation of the base.
- Setting it changes no rendering, no OOB swap, no cache behavior in this subtask. The flag is inert until #1013 wires it as one of three AND-ed conditions for stamping `hx-preserve="true"` onto a nested root (react-keys disjoint from the dirtied set; the id not itself a dirty/missing candidate in the same walk; `retain_across_parent_swaps` True on the owning class).

## Error paths

None. There is no validation, no coercion, and no rejection at class-definition time — a non-bool assignment is a static typing concern only, consistent with how the neighbouring ClassVars behave. No new exception types, no new messages.

## Tests

Tier per the test-placement rule at `docs/superpowers/rebuild/implementation-overview.md:59` ("Tests mirror the package: `tests/pyjinhx/test_<module>.py` per module, `tests/pyjinhx/reactive/` for the cluster"): all of these are unit tests in the mirrored-package tree, in the existing `tests/pyjinhx/reactive/test_reactive_component.py`, beside the other `ReactiveComponent` ClassVar tests (e.g. the `_pjx_cache_policy` tests already there).

1. `retain_across_parent_swaps` defaults to `True` on `ReactiveComponent` itself — `tests/pyjinhx/reactive/test_reactive_component.py`.
2. A subclass that does not mention the flag inherits `True` — same file.
3. A subclass assigning `retain_across_parent_swaps = False` reads back `False`, and `ReactiveComponent` still reads `True` (no base mutation) — same file.
4. Two sibling subclasses set it independently: one `False`, one left alone, and each keeps its own value — same file.

Not tested here: "a nested class with `retain_across_parent_swaps = False` -> no stamp, even when keys are disjoint" (milestone spec Testing section, lines 174-177). That is Story 1's end-to-end assertion and requires the wired `oob_swaps()` behavior, so it is owned by #1013.

---

# `ReactiveComponent.retain_across_parent_swaps` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare a public, per-class-overridable `retain_across_parent_swaps: ClassVar[bool] = True` on `ReactiveComponent`, with unit tests, and nothing reading it yet.

**Architecture:** A single class-body declaration in `pyjinhx/reactive/component.py`, placed in the existing ClassVar block beside `state_hash_exclude`, documented with a prose docstring directly below the assignment like every other ClassVar there. Because it is a plain inherited ClassVar overridden by reassignment in a subclass body — the same mechanism `state_hash_exclude` uses — no `__init_subclass__` / `__pydantic_init_subclass__` change is required, and no other module is touched.

**Tech Stack:** Python 3, pydantic (`BaseComponent` is a pydantic model base), pytest, ruff, basedpyright, uv.

**Spec:** `docs/superpowers/specs/issue-1011-design.md` (reproduced verbatim at the top of this file). Milestone-level design: `docs/superpowers/specs/2026-08-23-nested-reactive-oob-preserve-design.md:110-112`.

## Global Constraints

- Branch `m18/task-1011`, worktree `/home/mtts/Code/libs/pyjinhx/.claude/worktrees/m18/task-1011`, cut fresh from `origin/master`. Assume no code from #1012 or #1013 exists.
- Do NOT touch `pyjinhx/reactive/root_attrs.py` or `pyjinhx/reactive/fanout.py` — those are #1012 and #1013 territory.
- Do NOT add an `__init_subclass__` / `__pydantic_init_subclass__` hook for this flag.
- Exact new declaration, verbatim: `retain_across_parent_swaps: ClassVar[bool] = True`.
- No validation, no coercion, no new exception types or messages. A non-bool assignment is a static typing concern only.
- ClassVar convention in this file: `ClassVar[...]` annotation, class-level default, and a short prose docstring immediately below the assignment (a docstring, not an inline comment).
- Tests go in the mirrored-package tree only: `tests/pyjinhx/reactive/test_reactive_component.py` (rule at `docs/superpowers/rebuild/implementation-overview.md:59`). Not `tests/unit/`, `tests/integration/`, `tests/reactivity/`, or `tests/ui/`.
- Run each verification command as its own invocation; never chain them with `&&`.

---

### Task 1: Declare the `retain_across_parent_swaps` ClassVar

**Files:**
- Modify: `pyjinhx/reactive/component.py:60-62` (insert immediately after the `state_hash_exclude` docstring, before `_pjx_cache_policy` at line 64)
- Test: `tests/pyjinhx/reactive/test_reactive_component.py` (append to the end of the file, after `test_cache_alone_does_not_disturb_the_react_keys` at line 769-773)

**Interfaces:**
- Consumes: `ReactiveComponent` from `pyjinhx.reactive.component` — already imported at the top of the test file (line 10: `from pyjinhx.reactive.component import PjxKey, ReactiveComponent`). No new imports are needed in the test file.
- Note on the override syntax: a subclass reassigns the flag bare, with no re-annotation (`retain_across_parent_swaps = False`), because pydantic permits an un-annotated assignment when the name is an inherited ClassVar. That is exactly how `state_hash_exclude` is overridden today — see `tests/pyjinhx/reactive/test_reactive_state_hash.py:29` — so do not re-annotate it as `ClassVar[bool]` in the subclass bodies.
- Produces: `ReactiveComponent.retain_across_parent_swaps: ClassVar[bool]`, default `True`. #1013 will read it as `type(component).retain_across_parent_swaps`; this task only guarantees the attribute exists, defaults to `True`, and is overridden per-class by plain reassignment in a subclass body.

- [ ] **Step 1: Write the failing tests**

Append these four tests to the end of `tests/pyjinhx/reactive/test_reactive_component.py`, after `test_cache_alone_does_not_disturb_the_react_keys`:

```python
def test_retain_across_parent_swaps_defaults_to_true():
    assert ReactiveComponent.retain_across_parent_swaps is True


def test_retain_across_parent_swaps_is_inherited_by_a_silent_subclass():
    class Widget(ReactiveComponent):
        pass

    assert Widget.retain_across_parent_swaps is True
    assert Widget().retain_across_parent_swaps is True


def test_a_subclass_can_opt_out_of_retain_across_parent_swaps_without_mutating_the_base():
    class Widget(ReactiveComponent):
        retain_across_parent_swaps = False

    class Child(Widget):
        pass

    assert Widget.retain_across_parent_swaps is False
    assert Child.retain_across_parent_swaps is False
    assert ReactiveComponent.retain_across_parent_swaps is True


def test_sibling_subclasses_set_retain_across_parent_swaps_independently():
    class OptedOut(ReactiveComponent):
        retain_across_parent_swaps = False

    class Silent(ReactiveComponent):
        pass

    assert OptedOut.retain_across_parent_swaps is False
    assert Silent.retain_across_parent_swaps is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_component.py -k retain_across_parent_swaps -v`

Expected: all four FAIL with `AttributeError: type object 'ReactiveComponent' has no attribute 'retain_across_parent_swaps'` (or the same `AttributeError` named for the subclass).

- [ ] **Step 3: Write the minimal implementation**

In `pyjinhx/reactive/component.py`, insert the new declaration between the `state_hash_exclude` docstring (ends line 62) and `_pjx_cache_policy` (line 64), so the block reads:

```python
    state_hash_exclude: ClassVar[frozenset[str]] = frozenset({"id"})
    """Field names left out of the state hash. A subclass's value replaces this
    one outright rather than adding to it."""

    retain_across_parent_swaps: ClassVar[bool] = True
    """Whether this class's rendered region survives an ancestor's OOB swap
    untouched when nothing it depends on was dirtied. A subclass sets this to
    False to declare itself fully owned by its parent, so a parent swap always
    re-renders it rather than preserving what is on the page."""

    _pjx_cache_policy: ClassVar[CachePolicy | Literal[False] | None] = None
```

`ClassVar` is already imported at `pyjinhx/reactive/component.py:16`; add no imports.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_component.py -k retain_across_parent_swaps -v`

Expected: 4 passed.

- [ ] **Step 5: Run the tier-1 suite**

Run: `uv run pytest tests/pyjinhx/`

Expected: PASS, no new failures.

- [ ] **Step 6: Run the tier-2 suite**

Run: `uv run pytest tests/`

Expected: PASS, no new failures.

- [ ] **Step 7: Run the type checker**

Run: `uvx "basedpyright==1.39.9" pyjinhx/`

Expected: no new errors relative to `master`. `retain_across_parent_swaps` is a `ClassVar[bool]`, so a subclass assigning `= False` type-checks; assigning a non-bool is the static error the spec intends and needs no runtime guard.

- [ ] **Step 8: Format and lint**

Run: `ruff format .`

Then run: `ruff check .`

Expected: formatter reports nothing to reformat in the two touched files; `ruff check` passes.

- [ ] **Step 9: Commit**

```bash
git add pyjinhx/reactive/component.py tests/pyjinhx/reactive/test_reactive_component.py
git commit -m "feat: declare ReactiveComponent.retain_across_parent_swaps"
```

---

### Task 2: Full verification sweep

**Files:**
- No source changes expected. If a tier fails, fix the cause in `pyjinhx/reactive/component.py` or `tests/pyjinhx/reactive/test_reactive_component.py` only — do not touch `pyjinhx/reactive/root_attrs.py` or `pyjinhx/reactive/fanout.py`.

**Interfaces:**
- Consumes: `ReactiveComponent.retain_across_parent_swaps: ClassVar[bool]` from Task 1.
- Produces: nothing new; this task only proves the branch is green end to end.

- [ ] **Step 1: Run the docs build**

Run: `uv run mkdocs build --strict`

Expected: build succeeds. This task adds no docs page; the flag stays undocumented until #1013 gives it observable behavior worth documenting.

- [ ] **Step 2: Run the docs-field reference check**

Run: `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`

Expected: PASS. This check flags docs that name fields which do not exist; adding a field cannot break it.

- [ ] **Step 3: Run the package build**

Run: `uvx --from build python -m build`

Expected: sdist and wheel build successfully.

- [ ] **Step 4: Confirm no out-of-scope files were touched**

Run: `git diff --stat origin/master...HEAD`

Expected: exactly two files — `pyjinhx/reactive/component.py` and `tests/pyjinhx/reactive/test_reactive_component.py`. If `pyjinhx/reactive/root_attrs.py` or `pyjinhx/reactive/fanout.py` appear, revert those changes; they belong to #1012 and #1013.

- [ ] **Step 5: Commit anything the sweep fixed**

Only if steps 1-4 required a change:

```bash
git add pyjinhx/reactive/component.py tests/pyjinhx/reactive/test_reactive_component.py
git commit -m "fix: address verification failures for retain_across_parent_swaps"
```

If nothing changed, skip this step — the branch is already complete at Task 1's commit.
