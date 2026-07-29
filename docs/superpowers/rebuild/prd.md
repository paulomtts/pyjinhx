# PRD — pyjinhx 1.0 (engine rebuild)

Date: 2026-07-29 · Status: approved · Owner: Paulo
What "done" means for the rebuild. How is the RFCs' job; why is the ADRs'.

## Problem

Two perf campaigns (#221, #240) traced every superlinear render cost to one structural fact: each render level flattens children to a string, then re-derives structure by re-parsing it. Patching produced seven cache mechanisms, opacify token machinery, and one correctness concession (silent root-stamp fallback). The structure cannot be fixed incrementally — the #240 spec rejected single-pass rework as too risky against shipped invariants. Rebuild removes the fact instead of patching around it.

## Users

Primary: existing apps on pyjinhx 0.x (internal). Their migration cost and feature parity gate the release. Public adoption: welcome, not gating.

## Goals — all gating

| # | Goal | Measured by |
|---|---|---|
| G1 | Linear render scaling | Bench sweep: ms/component flat as tree grows to 10k components |
| G2 | Never slower than v0.36 | Same-page benchmark comparison, no regression on any bench case |
| G3 | Feature parity per port list | Every "keep"/"mod" in [feature-port-list.md](./feature-port-list.md) works; builtin suite green under v2 |
| G4 | Reactive behavior parity | ADR 0001 semantics preserved; v0.x reactive test suite passes |
| G5 | Migration is mechanical | Migration guide covers every breaking change; a v0.x app ports without redesign |
| G6 | Thread-safe by construction | Invariant 4 upheld; concurrent-request tests in CI from L2 |

## Non-goals

- SFC `{# python #}` blocks — dropped, not deferred
- Template-visible peer cross-reference — dropped (composition via nesting/slots only)
- String filters on component slots — opaque + truthiness only
- `.html`/`.jinja` extensions, kebab-case template names — `.pjx` + snake_case only
- Public `Parser`/`Tag` parse-tree API — segment types instead, no shim
- Cross-request InvalidationBackend, pjx-ls update — post-1.0
- New features beyond the port list — parity first, additions after 1.0

## Solution shape

Segment-list composition: a render level is an ordered list of markup segments; children are opaque nodes by construction; the root-tag span is recorded when output is produced. Invariants, mechanism map, and worked example: [architecture-overview.md](./architecture-overview.md).

```text
v0.36  render child → paste string into parent → RE-PARSE combined string
                                                  └─ superlinear + opacify machinery

v1.0   render child → opaque node in parent's segment list → join once at top
                                                  └─ O(S) parse total, no machinery
```

## Delivery

`src/pyjinhx2/` parallel package, same repo. Five layers, each shippable, each gated by its layer spec and ship criteria ([feature-port-list.md](./feature-port-list.md) assigns every feature to its layer):

```text
L0 kernel ──► L1 composition ──► L2 registry+assets ──► L3 reactivity ──► L4 builtins
   │               │                    │                    │                │
   bench          linear-scaling       concurrency          reactive         parity suite +
   baseline       proven (G1)          tests (G6)           parity (G4)      G2/G3/G5 close
```

At L4 close: package renamed, published as **pyjinhx 1.0**, migration guide shipped, v0.x frozen to critical fixes.

## Risks

| Risk | Mitigation |
|---|---|
| Slot opacity breaks real templates (filters on slots) | Grep builtins/docs before the L1 spec (ADR 0003's survey gate); if widespread, revisit before L1, not after |
| Minimal instance registry misses a reactive need | Enumerate reactivity's registry requirements before the L2 spec (ADR 0009's gate) |
| Parity gaps surface only at L4 | Builtins are the parity suite by design; L4 is the gate, not a formality |
| v0.x moves during rebuild | Port list pinned at 0.36.4; new v0.x features triaged into post-1.0 backlog |
