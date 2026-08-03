# ADR 0011: Process decisions — packaging, release, deferrals

**Status:** Accepted (packaging/specs 2026-07-28; release/deferrals 2026-07-29). Grouped: low-controversy calls that shape the project rather than the architecture.

## Parallel package, same repo

v2 was built under a temporary import name beside the current code. Shares tests, builtins, and CI; the builtins port validates each layer as it ships; v0.x keeps releasing throughout. Rejected: new repo (loses easy reuse of test suite and builtins during the port), long-lived v2 branch (permanent rebases against an active master). **Superseded by #539:** v2 now owns the `pyjinhx/` import path; the v0.x tree is staged at `pyjinhx_v0/` (and stays listed in `[tool.hatch.build.targets.wheel] packages`) purely so #540 can delete it in one move.

## Ships as pyjinhx 1.0

At L4 close — parity proven (PRD G3/G4), benchmarks green (G1/G2), migration guide shipped (G5) — the package is renamed and published as pyjinhx 1.0. v0.x freezes to critical fixes. Rejected: separate PyPI package forever (two products to maintain), deciding at L4 (the PRD needs a release vehicle to define "done").

## Layer specs written just-in-time

One RFC per layer, written when that layer starts, adversarially reviewed via /feature before implementation. Rejected: all layer specs up front — build-order layering means lower layers teach upper ones; deep-speccing reactivity before the kernel exists produces fiction.

## Cross-request InvalidationBackend deferred post-1.0

The per-request load cache ports in L3; the Redis/SQLite cross-worker invalidation backends do not gate 1.0. They are additive integrations with stable interfaces, and keeping two external-service integrations off the critical path shortens L3. Consuming apps needing them stay on v0.x until the post-1.0 port.

## Public `Parser`/`Tag` API dropped, no compat shim

v0.x exposes `Parser` and `Tag` for programmatic parse-tree access. v2's equivalent surface is the segment-model types (`RenderedLevel`, `ChildRef`, descriptor), which carry strictly more information (positions, spans, provenance). A shim reproducing the old tree shapes would preserve an API whose underlying model no longer exists. Migration note covers the handful of known uses.
