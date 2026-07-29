# ADR 0002: Segment-list composition; children opaque by construction

**Status:** Accepted, 2026-07-28. Foundational for the v2 rebuild (layer 0).

## Context

In v0.36, a parent renders children to strings, pastes them into its own output, then re-parses the combined string — once in `expand_custom_tags` and again in `apply_root_attrs` to find the root tag. Every superlinear term found across two perf campaigns (#221, #240) was a consequence: the opacify token machinery (protecting child output from re-parsing), its private-use-area collision bailout, the stamp-on-opacified-markup fix with its `try/except ValueError` full-restart fallback, and a user-visible correctness concession (multi-root templates silently stamp instead of raising). The #240 spec considered single-pass rework and rejected it — correctly, as too risky against shipped opacify/slot/asset invariants. A rebuild has no such invariants to protect.

## Options

1. **Keep bottom-up string composition, design opacify in from day one.** Preserves "slot values are real strings" fully; keeps the structural cost and all downstream machinery, just tidier.
2. **Hybrid: strings within a level, segments between levels.** Attempts both virtues; every seam between the two representations needs its own proof.
3. **Segment-list model.** A render level is an ordered list of segments — plain markup strings and opaque child nodes — produced by one parse over the level's own template output. The root-tag span is recorded during that same parse. Children are rendered levels spliced in as whole objects; serialization is one recursive join at the top.

## Decision

Option 3. A component's own template output is parsed exactly once, and that parse simultaneously cuts child-tag positions and records the root span. Children enter the parent as opaque nodes *by construction* — there is no code path through which a parent can see, re-parse, re-escape, or re-expand child markup as text.

## Consequences

- Total parse work per page is O(S) in output size; deep trees scale linearly (PRD G1).
- Opacify tokens, restore passes, the collision bailout, the second root-attr parse, and the `ValueError` fallback do not exist in v2. Root-attr and OOB stamping become string surgery at a recorded offset.
- Single-root violations raise again unconditionally — the v0.36 silent-stamp concession is reverted.
- Slot values are no longer real strings inside `template.render()` — forces ADR 0003.
- Worked example: [architecture-overview.md §5](../architecture-overview.md).
