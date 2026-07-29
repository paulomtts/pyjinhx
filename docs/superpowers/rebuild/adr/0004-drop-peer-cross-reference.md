# ADR 0004: Peer cross-reference dropped entirely

**Status:** Accepted, 2026-07-28.

## Context

v0.x lets a template reference a registered sibling by bare name — a name-miss in Jinja resolves against the request's instance registry. The same design was fixed three times: #72 (eager peer rendering — 32,784 renders for a 5-sibling page), #223 (per-node O(page) registry scans), #240 (O(n²) dict merge, replaced by lazy `_PjxContext.resolve_or_missing`, which itself landed through four regressions: async path, `{% include %}`, globals precedence, derived contexts). It also carries a documented footgun: a reactive component's kebab-default `id` silently shadowed by a same-named field (docs/guide/registry.md). The rebuild analysis leaned "keep, but make it an explicit API" (`{{ pjx.peer('save') }}`).

## Options

1. **Explicit API only** — `pjx.peer('save')` context global; O(1), scoped, no derived-context reasoning. Report's lean.
2. **Explicit + bare-name fallback** — migration ease, two paths to maintain.
3. **Drop entirely** — components compose only through nesting and slots.

## Decision

Option 3 — bolder than the report's lean, chosen deliberately. Cross-referencing is composition through a side channel; everything it does is expressible by passing the component (or its id) down the tree. Removing it deletes an entire class of machinery and reasoning rather than shrinking it.

## Consequences

- Deleted outright: `LazyNestedComponentWrapper`, `_PjxContext.resolve_or_missing`, `registry_defaults`/`registry_scanned` session plumbing, incremental registry folding, the shadowing footgun.
- Zero per-render cross-reference resolution cost — the mechanism behind three of the project's largest perf incidents does not exist in v2.
- Migration: v0.x templates using bare-name peer references must restructure to pass components explicitly. Breaking; covered by the 1.0 migration guide (PRD G5).
- The instance registry loses its template-facing role; what remains of it is governed by ADR 0009.
- The render cycle guard simplifies: cycles can only arise via nesting/`load()` chains.
