# pyjinhx v2 rebuild — doc index

The documentation set for rebuilding the pyjinhx engine as `src/pyjinhx2/`, shipping as pyjinhx 1.0. Everything here is local-only (gitignored with the rest of `docs/superpowers/`).

## The set

| Doc | Aim |
|---|---|
| [prd.md](./prd.md) | What "done" means: 6 gating goals, non-goals, delivery pipeline, risks. Written once; amended only on genuine scope change. |
| [adr/](./adr/README.md) | Why it's built this way: one decision per file (0001 pre-rebuild + 0002-0011), context/options/consequences. Immutable — superseded, never edited. New decisions during layer specs get recorded here at decision time. |
| [architecture-overview.md](./architecture-overview.md) | How it works: hard invariants, the mechanism-interaction map (mermaid), per-layer mechanisms with ship criteria, non-obvious interactions, worked example. *Living* — updated as layers ship; where it and reality disagree, fix the doc. |
| [feature-port-list.md](./feature-port-list.md) | What ships where: every v0.36 feature with keep/mod/drop verdict and its build layer. The G3 parity checklist; each layer spec must cover its assigned rows. |
| [implementation-overview.md](./implementation-overview.md) | How it lands as code: architecture style (flat module-per-mechanism + import rule), folder/file structure, render timelines (T0 startup / T1 cold / T2 reactive), load-bearing ordering facts. |
| [roadmap.md](./roadmap.md) | When and in what order: per-layer deliverables, PR-sized inner steps in dependency order, the two gates, checkboxes + recorded bench numbers. *Living* — check off as things ship. |

Per-layer design docs (RFC role) are not standalone artifacts — the /feature workflow's spec phase (brainstorm + adversarial-doc-review) produces each layer's design just-in-time, saved under `docs/superpowers/specs/`. Decided 2026-07-29.

## How they relate

```text
  PRD ─────────── what "done" means ──────────┐
   │                                          │
   │ constrains                               │ verified against
   ▼                                          ▼
  layer specs ── how each layer works ────► implementation
  (via /feature)                              │
   │ decisions extracted as                   │ reality feeds back into
   ▼                                          ▼
  ADRs ── why it's this way ──────► architecture-overview (living map)
```

## Background material

- [2026-07-28 rebuild-from-scratch analysis](../reports/2026-07-28-rebuild-from-scratch-analysis.md) — the source research: what v0.36 got right, what a rebuild changes, grounded in perf campaigns #221/#240.
- Superseded working docs (00-overview, segment-model-walkthrough, feature-layer-map, doc-plan) were merged into the four docs above on 2026-07-29.
