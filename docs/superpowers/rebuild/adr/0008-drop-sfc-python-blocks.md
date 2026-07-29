# ADR 0008: SFC `{# python #}` blocks dropped

**Status:** Accepted, 2026-07-29.

## Context

v0.x supports single-file components: a `{# python #}` block inside a template holding the component's Python class (pyjinhx PR #128, with LSP support in pjx-ls PR #1). It requires extracting and exec-ing embedded Python at discovery time, and couples template parsing to Python tooling (type-checking, LSP, import semantics for code that lives in a non-`.py` file).

## Options

1. **Port in the initial build** — parity, but exec machinery and LSP coupling land in the critical path.
2. **Defer post-L4** — keep the option open.
3. **Drop** — v2 does not have the feature.

## Decision

Option 3 — dropped, not deferred. The component-definition surface already has three well-supported shapes: class + adjacent template, classless `component()`, and `{#def#}`-headed templates. A fourth shape whose main cost is tooling coupling (exec at discovery, special-cased LSP, opaque-to-type-checkers code placement) doesn't pay for itself.

## Consequences

- No exec of template-embedded Python anywhere in v2 discovery.
- Migration: v0.x SFCs split into a `.py` class + adjacent `.pjx` template — mechanical, covered by the migration guide (PRD G5).
- pjx-ls's eventual v2 pass (post-1.0) drops its `{# python #}` support for v2 projects.
- If demand resurfaces, a new ADR reverses this with fresh context; nothing in v2's design forecloses it.
