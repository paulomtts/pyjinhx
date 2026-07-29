# ADR 0009: Instance registry minimal, reactivity-only

**Status:** Accepted, 2026-07-29. Depends on ADR 0004.

## Context

v0.x's request-scoped instance registry serves two masters: template-visible peer cross-reference (killed by ADR 0004) and reactivity's bookkeeping. With cross-reference gone, the open question was whether the instance registry survives at all. Reactivity's needs are real: OOB fan-out must resolve a mounted region's `{name, id}` (from the `X-PJX-Mounted` manifest) to something renderable, and hash-gating means a reactive region whose keys were *not* dirtied must be resolvable to its cached render rather than recomputed — the load cache is keyed by `(class, key)` and something must own that mapping per request.

## Options

1. **Drop the instance registry too** — reactivity rebuilds lookup structures ad hoc per request from the manifest; scattered ownership.
2. **Port it whole** — keeps machinery whose main consumer no longer exists.
3. **Minimal, reactivity-only** — a request-scoped (ContextVar) map from composite key (`name + id`) to instance/cached render, used exclusively by OOB fan-out and load-cache lookups. Not visible to templates, not consulted during ordinary rendering.

## Decision

Option 3. The registry becomes an implementation detail of layer 3 with its storage in layer 2: one owner for "what is mounted and what did it last render," nothing else. Its exact surface is enumerated before RFC-2 (PRD risk 2) — layer 2 builds only what that enumeration demands.

## Consequences

- Ordinary (non-reactive) rendering never touches the instance registry — zero cost on the common path.
- Composite keys and `request_scope` ContextVar isolation carry over from v0.x unchanged; both survived the #240 thread-safety audit untouched.
- Cached-render lookups for not-dirtied reactive regions have a single, named home.
- The pre-RFC-2 enumeration (swap targeting, manifest membership, hash inputs, cache keying) is the gate; anything it doesn't list doesn't get built.
