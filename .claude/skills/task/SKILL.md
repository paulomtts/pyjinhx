---
name: task
description: Use when the user says "/task <issue#>" or asks to pick up / work / implement a subtask card from the v2 board — drives one subtask issue end to end through spec, plan, adversarial validation, TDD implementation, review, tests, and PR + merge.
---

# /task — subtask pipeline

Drives ONE `subtask`-labeled issue from Backlog to Done. Board movement is NOT yours: at each transition you write `.claude/board-state.json` and the board-sync hook (sole holder of board permissions) moves the card and recomputes the parent story. Never call `gh project` mutations yourself.

## Stage writes

At each transition, write exactly this to `$CLAUDE_PROJECT_DIR/.claude/board-state.json` with the Write tool (the hook fires on Write|Edit, not shell redirects):

```json
{"issue": <N>, "stage": "<stage>"}
```

Stages, in order: `spec` → `ready` → `implementing` → `in-review` → `testing` → `done`.

## Pipeline

0. **Intake.** `gh issue view <N>` — confirm label `subtask` (a `story` gets refused: point user at its subtasks), read the parent story and its other sub-issues for context. Read the relevant rebuild docs: `docs/superpowers/rebuild/architecture-overview.md`, `implementation-overview.md`, the parent story body, and any ADRs it cites.
1. **Explore** → *write stage `spec`*. Dispatch an investigator subagent (cavecrew-investigator) over the modules/docs the subtask touches; keep only findings.
2. **Spec.** Short spec inline or in `docs/superpowers/specs/`: scope, observable behavior, error paths, test list. Scaled to subtask size — most subtasks need half a page.
3. **Plan.** Use superpowers:writing-plans, scaled down: ordered steps, each with its test.
4. **Validate** → *write stage `ready`*. Run adversarial-doc-review on spec+plan (kind:spec). Fold survivors back in before proceeding.
5. **Implement** → *write stage `implementing`*. Worktree (superpowers:using-git-worktrees), then strict TDD — **REQUIRED SUB-SKILL:** superpowers:test-driven-development. Commit granularly.
6. **Review.** cavecrew-reviewer on the branch diff. Fix real findings; re-run tests.
7. **Tests.** Full suite + typecheck (`uvx basedpyright`, standard mode). Then test-integrity-gate on the test diff vs merge-base. Gate failures = fix, not argue.
8. **PR + merge** → *write stage `in-review`*. Push, `gh pr create` (body links the issue: `Closes #<N>`), wait for checks, merge → *write stage `testing`*. Post-merge: run the suite on master.
9. **Close** → *write stage `done`*. Suite green on master closes the loop; the `Closes #` already closed the issue. Check off the matching roadmap item in `docs/superpowers/rebuild/roadmap.md` if the whole story completed.

## Rules

- One subtask per invocation. Don't drift into sibling subtasks — note follow-ups on their issues instead.
- Stage writes are mandatory and in order; skipping one leaves the card visibly stuck — that's the design, not a bug to work around.
- If blocked (spec contradiction, failing gate you can't fix honestly), write the current stage truthfully, comment findings on the issue, and stop.
