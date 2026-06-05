# Dependency-Aware Reactivity — Step 2 (Hash-Gating) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop re-sending reactive regions whose *value* did not actually change — even when a dependency they declared was dirtied — by comparing each region's freshly computed `state_hash()` against the hash the client reported in the `X-PJX-Mounted` manifest.

**Architecture:** Step 1 already stamps `data-pjx-hash` on every reactive root and the client already reports it, so the wire format is unchanged. This phase is purely server-side logic inside `oob_swaps()`: after reloading and rendering each dependency-matched region, drop the ones whose fresh hash exactly equals the reported hash (the "skip" permission), keeping everything else (the governing invariant: **when in doubt, swap**). Hash-gating runs **before** nesting-dedup so that an unchanged parent no longer suppresses a changed child.

**Tech Stack:** Python 3.13, Pydantic v2, Jinja2, MarkupSafe, pytest. No new dependencies; no client changes.

---

## Scope

This plan implements **only** Implementation Order step 2 from issue #12:

> Layer **hash-gating** on top.

Governing rules (from the issue):
- **Hash gating** = `state_hash() == reported` earns permission to *skip*. Missing / unknown / mismatched must always *swap*.
- **When in doubt, swap.**

**What changes:** `oob_swaps()` in `pyjinhx/reactive.py` (gate step + dedup reordering), its docstring, and `docs/reactivity.md` (the baseline is no longer "always-swap").

**What does NOT change:** the stamper, `state_hash()`, the renderer stamping, the client runtime, `Layout`, `client_script`, `PJX_MOUNTED_HEADER`, the public API surface, and the wire/manifest format. No client-side edits.

**Deferred (named, not built here):**
- **Step 3** — fold the walk into `render(*, dirtied=, mounted=)`, request duck-typing, auto-`load()` for dependents.
- **Step 4** — process-global `load()` cache + reverse index + `threading.Lock`.
- **Instance-keyed deps** (`"user:42"`).

---

## Design Notes (decisions locked here, not open questions)

**1. Gate condition.** For each dependency-matched, rendered region we have `fresh_hash = instance.state_hash()` (computed on the id-overridden instance — identical to the value the renderer just stamped) and `reported_hash = entry.get("hash")` from the manifest. The region is **swapped iff `fresh_hash != reported_hash`**. This naturally satisfies "when in doubt, swap":
- reported missing (`None`) → `None != "<hash>"` → swap.
- reported stale/different → swap.
- reported exactly equal → skip.

**2. Gate BEFORE dedup — and why ordering matters.** Walk through the four parent/child cases (markers nested in the rendered HTML):

| Parent | Child | Correct result | Mechanism |
| --- | --- | --- | --- |
| changed | changed | swap parent only (its fresh HTML already contains the child) | both pass gate → dedup drops child |
| changed | unchanged | swap parent only | parent passes gate; child gated out |
| **unchanged** | **changed** | **swap child on its own** | parent gated out → child is not nested in any *surviving* region → child survives dedup |
| unchanged | unchanged | swap nothing | both gated out |

The third row is the reason the gate must run first: in Step 1's order (dedup over *all* rendered candidates) the unchanged parent's HTML would still contain the child's marker and wrongly suppress the changed child. Gating first means `_drop_nested` only ever sees regions that are actually being swapped.

> Note: when a child is a Pydantic field of its parent (the common case, e.g. the `ReactivePanel(child=ReactiveCounter)` fixture), a child change also changes the parent's `model_dump_json()` and therefore the parent's hash — so "unchanged parent / changed child" only arises when the child is *not* part of the parent's serialized state (e.g. a separately-mounted, DOM-nested sibling). The gate-before-dedup ordering handles both shapes correctly.

**3. Hash is computed on the rendered instance.** `oob_swaps` sets `instance.id = component_id` before rendering; `state_hash()` includes `id` (via `model_dump_json`), and the renderer stamps `state_hash()` at that same point. Computing `fresh_hash = instance.state_hash()` after the id override keeps the gate value identical to the freshly stamped `data-pjx-hash`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `pyjinhx/reactive.py` *(modify)* | Introduce a small internal `_Candidate` dataclass carrying `id`/`html`/`fresh_hash`/`reported_hash`; capture the reported hash in the walk loop; add the gate step; run `_drop_nested` over the gated survivors; update `_drop_nested`'s signature and the `oob_swaps` docstring. |
| `docs/reactivity.md` *(modify)* | Replace the "always-swap baseline" framing with hash-gating; update the "Boundaries" list. |
| `tests/37_hash_gating_test.py` *(create)* | Hash-gating behavior + the gate-before-dedup interaction. |

No new fixtures are needed — the Step 1 fixtures `tests/ui/reactive/reactive_counter.py` (`ReactiveCounter`, id `counter`), `reactive_clear_button.py` (`ReactiveClearButton`, id `clear-btn`), `reactive_panel.py` (`ReactivePanel`, id `panel`, with a `ReactiveCounter` child) and `store.py` are reused.

**Test conventions:** numeric-prefixed `_test.py` files under `tests/`, run with `uv run pytest`. Compute expected hashes in tests by constructing/loading the same fixture instances and calling `.state_hash()`, so the test never hard-codes a digest.

---

## Task 1: Hash-gating in `oob_swaps()`

**Files:**
- Modify: `pyjinhx/reactive.py` (imports, `_drop_nested`, `oob_swaps`)
- Test: `tests/37_hash_gating_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/37_hash_gating_test.py`:

```python
from markupsafe import Markup

from pyjinhx import oob_swaps
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.reactive.reactive_panel import ReactivePanel


def _fresh_counter_hash() -> str:
    # Mirrors what oob_swaps computes: load() then id forced to the mounted id.
    instance = ReactiveCounter.load()
    instance.id = "counter"
    return instance.state_hash()


def _fresh_panel_hash() -> str:
    instance = ReactivePanel.load()
    instance.id = "panel"
    return instance.state_hash()


def test_matching_hash_is_skipped():
    store.state["remaining"] = 4
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": _fresh_counter_hash()}]
    out = oob_swaps({"todos"}, manifest)
    assert isinstance(out, Markup)
    assert str(out) == ""


def test_mismatched_hash_is_swapped():
    store.state["remaining"] = 4
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale-hash"}]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "4 left" in out


def test_missing_hash_is_swapped():
    store.state["remaining"] = 4
    manifest = [{"id": "counter", "type": "ReactiveCounter"}]  # no "hash" key
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='counter']" in out


def test_all_matching_returns_empty_markup():
    store.state["remaining"] = 7
    store.state["completed"] = 2
    clear = ReactiveClearButton.load()
    clear.id = "clear-btn"
    manifest = [
        {"id": "counter", "type": "ReactiveCounter", "hash": _fresh_counter_hash()},
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": clear.state_hash()},
    ]
    assert str(oob_swaps({"todos"}, manifest)) == ""


def test_unchanged_parent_does_not_suppress_changed_child():
    # Gate-before-dedup: the panel's hash matches (skip), but the nested counter's
    # reported hash is stale (changed) -> the counter must be swapped on its own,
    # and the panel must NOT be swapped.
    store.state["remaining"] = 9
    manifest = [
        {"id": "panel", "type": "ReactivePanel", "hash": _fresh_panel_hash()},
        {"id": "counter", "type": "ReactiveCounter", "hash": "stale-hash"},
    ]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='panel']" not in out
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "9 left" in out


def test_changed_parent_still_dedups_changed_child():
    # Both stale -> both "changed"; nesting dedup keeps only the parent swap.
    store.state["remaining"] = 3
    manifest = [
        {"id": "panel", "type": "ReactivePanel", "hash": "stale-a"},
        {"id": "counter", "type": "ReactiveCounter", "hash": "stale-b"},
    ]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='panel']" in out
    assert "outerHTML:[data-pjx-id='counter']" not in out
    assert "3 left" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/37_hash_gating_test.py -v`
Expected: FAIL — `test_matching_hash_is_skipped` and `test_all_matching_returns_empty_markup` fail (the current always-swap `oob_swaps` emits the region even though the hash matches); `test_unchanged_parent_does_not_suppress_changed_child` fails (current dedup order suppresses the changed child under the unchanged parent).

- [ ] **Step 3: Add the `_Candidate` dataclass and the dataclass import**

In `pyjinhx/reactive.py`, add `from dataclasses import dataclass` to the imports (place it with the stdlib imports, after `import json` / before `import logging`):

```python
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
```

Add the internal dataclass immediately above `_parse_mounted` (i.e. just after the `Layout._pjx_layout = True` line):

```python
@dataclass
class _Candidate:
    """A dependency-matched region that has been reloaded and rendered."""

    id: str
    html: str
    fresh_hash: str
    reported_hash: str | None
```

- [ ] **Step 4: Update `_drop_nested` to operate on `_Candidate`**

Replace the existing `_drop_nested` function in `pyjinhx/reactive.py`:

```python
def _drop_nested(candidates: list[_Candidate]) -> list[_Candidate]:
    """
    Drop any candidate whose data-pjx-id marker appears inside another candidate's
    HTML — the parent's fresh HTML already contains the child, so a separate swap
    would be redundant (and would fight the parent's swap).

    Runs only over regions that are actually being swapped (post hash-gate), so an
    unchanged parent never suppresses a changed child.
    """
    surviving: list[_Candidate] = []
    for index, candidate in enumerate(candidates):
        marker = f'data-pjx-id="{candidate.id}"'
        nested_in_other = any(
            marker in other.html
            for other_index, other in enumerate(candidates)
            if other_index != index
        )
        if not nested_in_other:
            surviving.append(candidate)
    return surviving
```

- [ ] **Step 5: Add the gate step and reorder dedup in `oob_swaps`**

Replace the body of `oob_swaps` from the rendering loop onward. The current code is:

```python
    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer(inline_js=False, inline_css=False)

    rendered: list[tuple[str, str]] = []
    seen_types: set[str] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        if not component_type or not component_id:
            continue

        component_class = classes.get(component_type)
        if component_class is None:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue
        if not (getattr(component_class, "_pjx_depends_on", frozenset()) & dirtied):
            continue

        if component_type in seen_types:
            logger.warning(
                "Multiple mounted instances of reactive type %s; the v1 "
                "type-singleton model reloads it once. Instance-keyed deps are "
                "deferred.",
                component_type,
            )
            continue
        seen_types.add(component_type)

        instance = component_class.load()
        instance.id = component_id
        rendered.append((component_id, str(instance._render(_renderer=renderer))))

    surviving = _drop_nested(rendered)
    if not surviving:
        return Markup("")

    fragments = [
        stamp_root_attributes(
            html, {"hx-swap-oob": f"outerHTML:[data-pjx-id='{component_id}']"}
        )
        for component_id, html in surviving
    ]
    return Markup("\n".join(fragments))
```

Replace it with:

```python
    classes = Registry.get_classes()
    renderer = Renderer.get_default_renderer(inline_js=False, inline_css=False)

    candidates: list[_Candidate] = []
    seen_types: set[str] = set()
    for entry in manifest:
        component_type = entry.get("type")
        component_id = entry.get("id")
        if not component_type or not component_id:
            continue

        component_class = classes.get(component_type)
        if component_class is None:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue
        if not (getattr(component_class, "_pjx_depends_on", frozenset()) & dirtied):
            continue

        if component_type in seen_types:
            logger.warning(
                "Multiple mounted instances of reactive type %s; the v1 "
                "type-singleton model reloads it once. Instance-keyed deps are "
                "deferred.",
                component_type,
            )
            continue
        seen_types.add(component_type)

        instance = component_class.load()
        instance.id = component_id
        html = str(instance._render(_renderer=renderer))
        candidates.append(
            _Candidate(
                id=component_id,
                html=html,
                fresh_hash=instance.state_hash(),
                reported_hash=entry.get("hash"),
            )
        )

    # Hash-gate first: skip only regions whose freshly computed state hash exactly
    # matches the hash the client reported (its DOM value is already current).
    # Missing/unknown/mismatched all fall through to a swap ("when in doubt, swap").
    # Gating before dedup ensures an unchanged parent never suppresses a changed child.
    changed = [c for c in candidates if c.fresh_hash != c.reported_hash]

    surviving = _drop_nested(changed)
    if not surviving:
        return Markup("")

    fragments = [
        stamp_root_attributes(
            c.html, {"hx-swap-oob": f"outerHTML:[data-pjx-id='{c.id}']"}
        )
        for c in surviving
    ]
    return Markup("\n".join(fragments))
```

- [ ] **Step 6: Update the `oob_swaps` docstring**

In `pyjinhx/reactive.py`, replace the second paragraph of the `oob_swaps` docstring. Current text:

```python
    This is the always-swap baseline (issue #12, implementation order step 1):
    every region depending on a dirtied key is reloaded and swapped. Hash-gating
    (skipping regions whose value did not change) is layered on in step 2.
```

Replace with:

```python
    Dependency-filtered and hash-gated (issue #12, implementation order steps
    1-2): a region depending on a dirtied key is reloaded, and an OOB swap is
    emitted only if its freshly computed state hash differs from the hash the
    client reported for it. A matching hash earns permission to skip; a missing
    or mismatched hash always swaps ("when in doubt, swap").
```

- [ ] **Step 7: Run the new test to verify it passes**

Run: `uv run pytest tests/37_hash_gating_test.py -v`
Expected: PASS (6 passed).

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS. Note: the Step 1 `tests/35_oob_swaps_test.py` cases use deliberately non-matching reported hashes (e.g. `"hash": "stale"`, `"x"`), so they still swap and remain green under gating.

- [ ] **Step 9: Lint**

Run: `uvx ruff check pyjinhx/reactive.py tests/37_hash_gating_test.py`
Expected: `All checks passed!`
Run: `uvx ruff format pyjinhx/reactive.py tests/37_hash_gating_test.py`
Expected: files formatted (or already formatted).

- [ ] **Step 10: Commit**

```bash
git add pyjinhx/reactive.py tests/37_hash_gating_test.py
git commit -m "feat(reactive): hash-gate oob_swaps to skip unchanged regions"
```

---

## Task 2: Documentation

**Files:**
- Modify: `docs/reactivity.md`

- [ ] **Step 1: Update the intro framing**

In `docs/reactivity.md`, replace the paragraph at lines 8-10:

```markdown
This is the **always-swap baseline**: every region that depends on a dirtied key
is reloaded and swapped. (Hash-gating to skip unchanged regions, `render()`
integration, and a `load()` cache are planned follow-ups.)
```

with:

```markdown
A region that depends on a dirtied key is reloaded and re-emitted **only when its
value actually changed** — its freshly computed `state_hash()` is compared against
the hash the client reported, and a matching hash is skipped. (`render()`
integration and a `load()` cache are planned follow-ups.)
```

- [ ] **Step 2: Update the `oob_swaps` behavior list**

In `docs/reactivity.md`, replace the bullet list at lines 85-89:

```markdown
`oob_swaps`:
- keeps only mounted regions whose `depends_on` intersects `dirtied`,
- calls each region's `load()` and re-renders it,
- drops any region nested inside another swapped region (the parent already contains it),
- returns concatenated `hx-swap-oob` fragments (empty if nothing matched).
```

with:

```markdown
`oob_swaps`:
- keeps only mounted regions whose `depends_on` intersects `dirtied`,
- calls each region's `load()` and re-renders it,
- skips a region whose freshly computed `state_hash()` matches the hash the client
  reported (its DOM value is already current); a missing or mismatched hash always
  swaps — *when in doubt, swap*,
- drops any region nested inside another swapped region (the parent already contains it),
- returns concatenated `hx-swap-oob` fragments (empty if nothing changed).
```

- [ ] **Step 3: Update the Boundaries section**

In `docs/reactivity.md`, replace the "Boundaries" section heading and its first bullet (lines 95-97):

```markdown
## Boundaries (current baseline)

- **Always-swap**: hash-gating is not applied yet — a matching region is always re-sent.
```

with:

```markdown
## Boundaries

- **Hash gating is a skip-hint, not correctness authority**: a matching client hash
  earns permission to skip; missing/unknown/mismatched always swaps. It saves
  bandwidth and DOM churn, not database work (a short-circuiting `load()` cache is a
  later phase).
```

(Leave the remaining two bullets — Type-singleton and `mounted` accepts — unchanged.)

- [ ] **Step 4: Verify docs build (if mkdocs available) and the suite is still green**

Run: `uv run pytest tests/ -q`
Expected: PASS.
Run (optional): `uv run mkdocs build --strict` then remove the generated `site/` directory.
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add docs/reactivity.md
git commit -m "docs(reactive): document hash-gating behavior"
```

---

## Final: Push

- [ ] **Run the full suite + lint one more time**

Run: `uv run pytest tests/ -q` → PASS
Run: `uvx ruff check .` → `All checks passed!`

- [ ] **Push to the existing branch (updates the merged-feature follow-up)**

The Step 1 work merged via PR #13. Create a fresh branch for Step 2 off the latest `master` (do not reopen the merged branch):

```bash
git checkout master && git pull origin master
git checkout -b claude/issue-12-step2-hash-gating
git push -u origin claude/issue-12-step2-hash-gating
```

(Retry pushes on network errors with exponential backoff: 2s, 4s, 8s, 16s. Do NOT open a PR unless asked.)

---

## Self-Review

**Spec coverage (issue #12, step 2 — "Layer hash-gating on top"):**
- Reload + compare fresh `state_hash()` vs reported, swap only on differ — Task 1 Step 5. ✅
- Missing/unknown/mismatched → swap ("when in doubt, swap") — covered by `fresh_hash != reported_hash` with `reported_hash = entry.get("hash")` (None on missing); tested by `test_missing_hash_is_swapped`, `test_mismatched_hash_is_swapped`. ✅
- Matching → skip — `test_matching_hash_is_skipped`, `test_all_matching_returns_empty_markup`. ✅
- Nesting dedup preserved and corrected under gating — `_drop_nested` reorder; `test_unchanged_parent_does_not_suppress_changed_child`, `test_changed_parent_still_dedups_changed_child`. ✅
- No wire/client changes — confirmed: only `reactive.py` + docs touched. ✅

**Type/name consistency:**
- `_Candidate(id, html, fresh_hash, reported_hash)` defined in Task 1 Step 3; consumed in Steps 4-5 with matching attribute names. ✅
- `_drop_nested(list[_Candidate]) -> list[_Candidate]` — signature updated (Step 4) and called with `changed` (a `list[_Candidate]`) in Step 5. ✅
- `entry.get("hash")` returns `str | None`, matching `_Candidate.reported_hash: str | None`. ✅
- Fixture names/ids used in tests (`ReactiveCounter`/`counter`, `ReactiveClearButton`/`clear-btn`, `ReactivePanel`/`panel`) match the Step 1 fixtures. ✅

**Placeholder scan:** No TBD/TODO/"add error handling"/"similar to Task N" — every code step shows complete code. ✅

**Interaction check (gate vs dedup):** The four-case table in Design Notes is exercised by tests — rows 1 (`test_changed_parent_still_dedups_changed_child`), 3 (`test_unchanged_parent_does_not_suppress_changed_child`), and 4 (`test_all_matching_returns_empty_markup` covers the all-unchanged shape). Row 2 (changed parent / unchanged child) reduces to row 1's mechanism (parent swaps, child not separately emitted) and is implicitly covered. ✅
