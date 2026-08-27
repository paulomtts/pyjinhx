# Issue #1051 — Tooltip never becomes visible inside an open `<dialog>`

Standalone bug subtask (label `subtask`, no parent story, no sibling sub-issues). Scope is one file plus one new test file.

## Problem

`PJXTooltip` renders and wires correctly, but when the tooltip root sits inside an open `<dialog>` (in practice `PJXDrawer`, which calls `showModal()`), hovering or focusing the trigger does not make the tip appear. Observed state after hover: the tip has had its `hidden` attribute removed (`pjx_tooltip.js:169`) but never gains `pjx-tooltip__tip--visible`, so `pjx_tooltip_content.css:14-15` keeps it at `visibility: hidden; opacity: 0`. The class is added at `pjx_tooltip.js:175`, inside the `requestAnimationFrame` callback opened at line 173 — the same callback that first calls `place(tip, root)` at line 174. Any throw or non-return inside `place()` therefore silently skips both the visible class and the backdrop's visible class at line 176; the browser swallows the exception in the rAF callback and the failure presents as "nothing happened".

The reporter's suspicion — to be verified against a real browser, not assumed — is that `place()` → `boundsFor()` (`pjx_tooltip.js:59-85`) misbehaves when the trigger's ancestor chain passes through a top-layer `<dialog>`. The relevant code is the walk at line 71, `while (node && node !== document.documentElement)`, calling `getComputedStyle(node)` per ancestor; the drawer contributes `overflow: clip` at `pjx_drawer.css:38`, which is the first non-`visible` overflow the walk will hit.

## Scope

In scope:

- `pyjinhx/builtins/ui/pjx_tooltip/pjx_tooltip.js` — `show()`, `place()`, `boundsFor()` only.
- One new co-located browser test file for the dialog-nesting concern.

Out of scope (explicitly deferred; the issue author separates it from this bug):

- The `portal="true"` painting problem. `portalTip()` (`pjx_tooltip.js:31-35`) reparents the tip to `document.body`, which is outside the dialog's top-layer stacking context, so a portalled tip paints behind the modal regardless of `z-index`. Do not attempt a top-layer/portal-target redesign here.
- Any change to `PJXDrawer`, its CSS, or `PJXModal`.
- Any change to backdrop lifecycle semantics beyond the incidental fact that line 176 runs in the same callback.

## Observable behavior after the fix

1. A tooltip root nested anywhere inside an open `<dialog>` (including inside a `overflow: clip` box within it), with `portal` unset, gains `pjx-tooltip__tip--visible` on the tip on `mouseover` of the trigger and on `focusin` of the trigger, on the frame after `show()` runs.
2. The tip's computed `visibility` is `visible` and `opacity` is `1` once the transition settles — i.e. it actually paints, not merely carries the class.
3. Placement inside the dialog stays correct: the tip is clamped/flipped against the dialog's clipping box intersected with the viewport, exactly as it already is for a plain in-page clipping ancestor. No regression in the cases owned by `test_pjx_tooltip_collision.py`.
4. `hide()` still removes the class and re-sets `hidden` for the dialog-nested case; a second hover re-shows it.
5. Backdrop behavior (when a backdrop element is present) is unchanged: it gains and loses `pjx-tooltip__backdrop--visible` in step with the tip.

## Error paths

- `place()` must not be able to prevent the tip from becoming visible. Whatever the specific dialog-related defect turns out to be, a measurement failure is a degraded-position problem, not a hidden-tooltip problem: `show()` must still end with the tip carrying `pjx-tooltip__tip--visible` (and the backdrop its own visible class).
- Missing trigger: `place()` already returns early at line 94 when `.pjx-tooltip__trigger` is absent. Under the fix that early return must likewise not suppress the visible class.
- Dialog closed while a tip is showing: no crash, no leaked `activeTip`/`activeRoot`/`activeBackdrop` state that would block the next `show()` on another root.
- Non-modal `<dialog open>` (no `showModal()`) must behave the same as the modal case.

## Constraints

- Keep `place()` and `boundsFor()` as plain module-scope functions inside the existing IIFE — pure transforms stay functions, no class wrapper (CONVENTIONS rule 4).
- Any new helper lives in `pjx_tooltip.js` itself, not in a new shared module (CONVENTIONS rule 7).
- No ADR governs tooltip/dialog interaction; `docs/decisions/` holds only ADR 0001 (OOB swaps) and ADR 0002 (cache backend), neither relevant.
- Comments explain WHY, docstrings explain WHAT; no PR/issue references in code comments.

## Tests

Test-placement rule for this repo (established by precedent in `tests/pyjinhx/builtins/pjx_tooltip/`, restated in each file's module docstring): tests are **co-located per component** under `tests/pyjinhx/builtins/<component>/`, mirroring the source tree — there is no separate `tests/ui/` or `tests/integration/` tier in use (those directories contain only stale `__pycache__`). Each file owns one narrow concern and declares it in its docstring. Browser tests use real Playwright + the real shipped controller loaded via `page.add_script_tag(content=CONTROLLER.read_text())`, never a JS stub, and carry the `_require_chromium` autouse fixture that skips rather than fails when chromium is absent.

Dialog nesting is a new concern owned by none of the existing siblings (`test_pjx_tooltip.py` = server-rendered markup/props, `test_pjx_tooltip_collision.py` = clamp/flip placement math, `test_pjx_tooltip_backdrop.py` = backdrop visibility lifecycle, `test_pjx_tooltip_trigger.py` / `test_pjx_tooltip_content.py` = their own server-rendered markup). It therefore gets a new file: **`tests/pyjinhx/builtins/pjx_tooltip/test_pjx_tooltip_dialog.py`** — co-located component tier, real Chromium. Do not add these cases to the collision or backdrop files.

All tests below belong to that one new file, in the co-located `tests/pyjinhx/builtins/pjx_tooltip/` tier:

1. **Regression, modal dialog, hover** — trigger inside `dialog.showModal()`; `mouseover` the trigger; the tip has `pjx-tooltip__tip--visible`. Fails before the fix.
2. **Regression, modal dialog, computed style** — same fixture; after the transition, computed `visibility == "visible"` and `opacity == "1"`, proving it paints and not just class-flips.
3. **Keyboard path** — `focusin` on the trigger inside the open dialog produces the same visible class, so the fix is not hover-specific.
4. **Clipping ancestor inside the dialog** — trigger inside an `overflow: clip` box inside the dialog (mirrors `pjx_drawer.css:38`); tip becomes visible *and* its rendered box stays inside that box ∩ viewport, confirming the fix did not simply bypass bounds.
5. **Non-modal `<dialog open>`** — same visible-class assertion, showing the behavior is not tied to `showModal()`/top layer.
6. **Hide and re-show** — `mouseout` removes the visible class and restores `hidden`; a second `mouseover` re-adds the visible class.
7. **Backdrop stays in step** — with a `.pjx-tooltip__backdrop` present inside the dialog, it gains and loses `pjx-tooltip__backdrop--visible` together with the tip (guards the shared rAF callback at `pjx_tooltip.js:173-177`).
8. **No regression outside a dialog** — the existing `tests/pyjinhx/builtins/pjx_tooltip/test_pjx_tooltip_collision.py` and `test_pjx_tooltip_backdrop.py` pass unchanged; no edits to either file.

## Verification

CI is the source of truth (`.github/workflows/tests.yml`, `.github/workflows/ruff.yml`). Run these as separate invocations:

- `uvx "basedpyright==1.39.9" pyjinhx/`
- `ruff format .`
- `ruff check .`
- `uv run playwright install --with-deps chromium`
- `uv run pytest tests/pyjinhx/`
- `uv run pytest tests/`
- `uv venv .venv-min && uv pip install --python .venv-min . pytest && .venv-min/bin/python -m pytest tests/minimal/ -q` (distinct CI leg; this JS-only fix should not touch import-time behavior)

## Board note

Issue #1051 has no project card on `PVT_kwHOBZmM8c4BewiO` (`projectItems` is empty), so no Status mutation was possible and none was attempted. With no parent story there is nothing to mirror.
