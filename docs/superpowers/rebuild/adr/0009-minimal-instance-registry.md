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
- The pre-RFC-2 enumeration (swap targeting, manifest membership, hash inputs, cache keying) is the gate; anything it doesn't list doesn't get built. That enumeration is now recorded below under **Enumerated Surface** (E1-E18) — it is the binding list for L2.

## Enumerated Surface

This is the gate named in Consequences, filled in. It consolidates the swap-targeting enumeration from [#382](https://github.com/paulomtts/pyjinhx/issues/382) (R1-R7) and the manifest/hash/cache enumeration from [#383](https://github.com/paulomtts/pyjinhx/issues/383) (R1-R12); the per-item v0.x traceability lives in those subtasks' scratch analyses. L2 builds exactly this and nothing more.

Three mechanisms collaborate and stay separate: the **instance registry** answers "what is mounted under this key and what did it last render," the **LoadCache** answers "does `load()` need to rerun," and the **hash gate** answers "did the output actually change." Merging any two of them is out of scope for L2.

1. E1. Resolve a composite key `{type, id}` to exactly one of: a live instance, a cached `RenderedLevel` (with its recorded `root_span`), or a miss. (#382 R1)
2. E2. Swap-target identity is outerHTML-only: the target of a swap is the region the key resolves to, replaced whole. (#382 R2; ADR 0001)
3. E3. Splicing happens at the `root_span` recorded at render time; the registry never re-parses rendered HTML to locate a target. (#382 R4; Invariant 1)
4. E4. A miss is observably distinguishable from a clean resolve at the call site, from a single lookup. (#382 R3; representation decided below)
5. E5. The registry exposes no containment or nesting API — structural containment (what is inside what) is owned by the segment tree, not by the registry. (#382 R5, N5)
6. E6. Registry storage is request-scoped: a `ContextVar` reset by `request_scope`, inside the Invariant 4 census, adding no state beyond it. (#382 R6, #383 R7)
7. E7. Single writer: entries are written only by the Load path. OOB fan-out is a read-only consumer. (#382 R7)
8. E8. A manifest entry carries exactly `{type, id, load, hash}` — no other fields are required by reactivity. (#383 R1)
9. E9. Two independent filter predicates run before any load or hash work: (a) does `type` resolve to a known component class, (b) does the entry's reactive-key set intersect the dirtied keys. (#383 R2)
10. E10. Surviving entries are deduplicated by `(type, load_arg)` before load runs. (#383 R3)
11. E11. Hash inputs compose from component state: stable across identical state, sensitive to any state change, computed without re-parsing rendered output, and supporting per-field exclusion (v0.x's `state_hash_exclude`). (#383 R4)
12. E12. The hash gate is a single equality comparison against the manifest's `hash`, applied as an independent second gate after the key filter — not folded into E9. (#383 R5)
13. E13. The LoadCache key is `(component_class, load_arg)`. It is a different key space from the registry's `(name, id)` and the two are never merged. (#383 R6, N5)
14. E14. Invalidation is by reactive key through a reverse index from key to affected cache entries — never by iterating the manifest. (#383 R8)
15. E15. A keyed component's reactive-key set is the union of its static `react` keys and its per-key derived keys, and that one set is the single source of truth for both the E9 filter and cache eviction. (#383 R9)
16. E16. One shared key-coercion path normalizes `MutationKey`, plain strings, and dynamic keys; every consumer above goes through it. (#383 R10)
17. E17. Miss handling composes with the cache: a key that no longer resolves must not yield a stale cached instance or render. (#382 R3, #383 R11)
18. E18. No re-parsing of rendered HTML anywhere across registry resolve, manifest handling, hash computation, or cache lookup. (#383 R12; restates Invariant 1)

### Ruled out (non-requirements)

These are named so a future reader can tell "absent because unneeded" from "absent because forgotten." Building any of them in L2 is out of scope.

1. N1. Template-visible registry lookups of any kind — the registry stays template-invisible. (ADR 0004)
2. N2. Append, prepend, or delta swap modes. (ADR 0001)
3. N3. A second HTML parse to recover structure, spans, or containment. (Invariant 1)
4. N4. A pluggable custom-hash-function API — hash composition is fixed, with field exclusion as the only knob. (E11)
5. N5. Merged registry/cache keying, or any single "universal key." (E13)
6. N6. A process-wide cache as a mandate. (See the cache-scope decision below.)
