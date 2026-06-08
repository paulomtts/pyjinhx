---
name: code-audit-sweep
description: >-
  Orchestrate a full structural code audit of pyjinhx using seven focused lenses
  (file responsibility, module placement, domain entities, state shape, duplication,
  indirection, public API). Use when the user asks to "audit the codebase", "sweep
  for quality", "review architecture", "audit reactive/", or before a large PR merge.
  Produces a merged read-only report; remediation is a separate pass unless requested.
disable-model-invocation: true
---

# Code audit sweep

## Audit ownership

**I own:** running all child audits in order, merging reports, deduplicating findings at the same location, and delivering one prioritized punch list.

**I don't own:** individual lens rules (→ child skills), idempotency/retry safety (→ external audits), test coverage gaps.

**Defer to:** child skill named in each finding for fix guidance.

Read shared rules: [CONVENTIONS.md](CONVENTIONS.md).

## Workflow

1. **Confirm scope** — default `pyjinhx/`; user may narrow (e.g. `pyjinhx/reactive/`).
2. **Run child audits in order** (read and follow each skill):
   - [file-responsibility-audit](../file-responsibility-audit/SKILL.md)
   - [module-placement-audit](../module-placement-audit/SKILL.md)
   - [domain-entity-audit](../domain-entity-audit/SKILL.md)
   - [state-shape-audit](../state-shape-audit/SKILL.md)
   - [duplication-audit](../duplication-audit/SKILL.md)
   - [indirection-audit](../indirection-audit/SKILL.md)
   - [public-api-audit](../public-api-audit/SKILL.md)
3. **Merge** — same file:line → one finding, highest severity, note all lenses.
4. **Output** combined report using CONVENTIONS template + executive summary table:

| P1 | P2 | P3 | Scope |
|----|----|----|-------|

5. **Do not fix** unless user asks.

## Single-lens runs

If the user names one lens only (e.g. "indirection audit on this PR"), run that child skill alone; skip merge step.

## Expected baselines (post reactive refactor)

- `pyjinhx/reactive/` — expect zero P1 if refactor landed; P3 doc nits OK.
- `pyjinhx/core/` — likely P2/P3 backlog (renderer size, module-level autodiscover helpers).

Use dry-run results to calibrate; do not suppress real findings to match baselines.
