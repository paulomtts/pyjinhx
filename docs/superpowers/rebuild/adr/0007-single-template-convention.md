# ADR 0007: One template convention — `.pjx` + snake_case

**Status:** Accepted, 2026-07-28.

## Context

v0.x probes six filename candidates per tag: three extensions (`.pjx`, `.html`, `.jinja`) × two case conventions (snake_case, kebab-case). This produced 10,524 `get_template` calls for 1,754 components (#240 plan, Task 4), fixed with per-tag caches (#225) — a cache that exists only because the probe matrix does. The rebuild analysis called it "a perfect miniature of the whole story": small decision, structural cost, machinery to compensate.

## Options

1. **Keep all six probes** — full naming freedom, keep the cache machinery.
2. **One extension, one case** — `.pjx` + snake_case; one probe per lookup.
3. **Drop discovery entirely** — explicit registration; destroys the Tier 1 "drop a template in a folder" experience the docs sell.

## Decision

Option 2. Filesystem discovery is product positioning and stays (docs/guide/usage-tiers.md); the probe matrix is engineering debt and goes. A 1×1 matrix needs no cache. `.pjx` wins over `.html`/`.jinja` because it is already first in v0.x's probe order, is the extension pjx-ls targets, and unambiguously identifies pyjinhx templates.

## Consequences

- One filesystem probe per class per kind (template/css/js), paid once at registration into the descriptor. The per-tag probe caches (#225) and most of `Finder`'s candidate logic do not exist in v2.
- Migration: v0.x projects with `.html`/`.jinja` templates or kebab-case names rename files. Mechanical (a shell one-liner), covered by the migration guide (PRD G5).
- MRO resolution (ADR 0010) also shrinks: one candidate per ancestor instead of six.
