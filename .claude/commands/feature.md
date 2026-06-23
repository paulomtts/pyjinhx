---
description: Implement a feature end-to-end — brainstorm, adversarially review the spec & plan, implement, and run a test-integrity gate before finishing.
argument-hint: <feature description>
---

# /feature — feature-implementation workflow

You are driving the full feature lifecycle for: **$ARGUMENTS**

Follow these steps IN ORDER. Emit a short summary after each step. Do not skip the gates. Invoking the Workflow scripts below is an explicit instruction of this command (the user opted in by running `/feature`).

## 0. Branch
- Run `git branch --show-current`.
- If on `master`, or on a branch clearly unrelated to this feature, create one off `master`: `git checkout -b feature/<slug> master` (derive `<slug>` from the description). Otherwise confirm the current branch is the intended home and continue.

## 1. Brainstorm (interactive)
- Invoke the `superpowers:brainstorming` skill with the feature description. Participate with the human. It ends by writing a spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and a user-review gate.
- Record the spec path as **SPEC**.

## 2. Adversarial spec review (autonomous)
- Dispatch: `Workflow({ name: 'adversarial-doc-review', args: { kind: 'spec', docPath: SPEC, specPath: SPEC } })`.
- When it returns: if `findings` is non-empty, fold them into ONE revision round of the spec (edit the spec file to address each), then show the human a concise diff + a table of findings and how each was addressed. This step informs; it never blocks.

## 3. Plan (interactive)
- Invoke the `superpowers:writing-plans` skill against SPEC. It writes a plan to `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.
- Record the plan path as **PLAN**.

## 4. Adversarial plan review (autonomous)
- Dispatch: `Workflow({ name: 'adversarial-doc-review', args: { kind: 'plan', docPath: PLAN, specPath: SPEC } })`.
- If `findings` non-empty: fold into ONE revision round of the plan, show diff + summary. Never blocks.

## 5. Implement
- Invoke the `superpowers:subagent-driven-development` skill to implement PLAN task-by-task.

## 6. Test-integrity gate (autonomous judge + remediation loop)
This is the critical gate. Do NOT declare the feature done until it PASSES or HARD-STOPS to the human.

### 6a. Compute the baseline diff
- `BASE=$(git merge-base HEAD master)`
- A "test file" matches `tests/**`, `test_*.py`, or `*_test.py`.
- `git diff --name-status "$BASE" -- 'tests/**' 'test_*.py' '*_test.py'`
- Classify by status: **M → modified**, **D → deleted**, **A → new**.
- For each file capture its diff: `git diff "$BASE" -- <path>` (deleted → the removed content; new → the full added content).

### 6b. Run the judge
- Build `items = [{ id, category, path, diff }, ...]` and dispatch:
  `Workflow({ name: 'test-integrity-gate', args: { specPath: SPEC, planPath: PLAN, items } })`.
- It returns `{ items, violations }`. If `violations` is empty → gate PASSES; go to step 7.

### 6c. Remediate (bounded loop, max N = 3 iterations)
For each violation, apply ONLY the allowed remediation — NEVER satisfy the gate by weakening or re-justifying a test:
- **modified or deleted existing test, not spec/plan-justified** → restore the original: `git checkout "$BASE" -- <path>`. Then dispatch a subagent to FIX THE IMPLEMENTATION so the restored test passes honestly. The subagent may NOT touch the test.
- **hollow new test** → dispatch a subagent to STRENGTHEN the new test so it exercises real behavior (allowed: it is a new test, not an existing contract).
- After remediating all violations, re-run steps 6a–6b.
- **Genuine conflict** — a restored test fails, there is NO spec/plan basis for changing it, AND the implementation cannot pass it honestly → STOP. Report the conflicting tests, the judge's reasons, and the relevant spec sections to the human. This decision is the human's.
- If the loop exceeds N iterations without converging → STOP and report.

## 7. Finish
- Once the gate passes, invoke the `superpowers:finishing-a-development-branch` skill to present merge/PR options and complete the work.

## Reporting
Surface every finding and every violation — never silently drop one.
