# L1.G.2 gate: enumerate manifest/hash/cache needs

Input to #384 (record enumeration in ADR 0009). Analysis only: no code, no ADR edit, no roadmap edit. Companion half is #382 (swap targeting, closed, merged as `docs/superpowers/rebuild/scratch/382-swap-targeting-needs.md`) — deliberately absent here.

This document answers exactly one question: what must the request-scoped instance registry / LoadCache / hashing surface expose for (a) manifest membership, (b) hash inputs, (c) cache keying? Anything not listed here is not built (ADR 0009: "anything it doesn't list doesn't get built").

## Source grounding

- `pyjinhx/reactive.py:284-295` — `state_hash()`: SHA-256 hex digest over canonical JSON (`sort_keys=True, separators=(",", ":")`) of `model_dump(mode="json", exclude=state_hash_exclude)`; `id` excluded by default. This is the hash-input composition v2 must keep.
- `pyjinhx/client.py:140-165` (`MountedManifest.parse`, called at `pyjinhx/reactive.py:443`) — parses `X-PJX-Mounted` into a `list[dict]`; the entry shape `{type, id, load, hash}` is not type-checked by `parse` itself but is the shape every caller (the fan-out loop below) reads off each entry. This is the manifest-membership surface: what a mounted region reports about itself.
- `pyjinhx/reactive.py:421-425` — `_manifest_load_arg`: extracts the `load` key from a manifest entry for keyed-component dispatch.
- `pyjinhx/reactive.py:455-486` — per-entry loop: class lookup by `type`, keyed/unkeyed `load` dispatch, `_pjx_reacts_to` static keys unioned with `_keyed_derived_keys` for keyed components, dedup by `(component_type, load_arg)`, intersected against dirtied keys. This is the manifest-entry-to-candidate filter.
- `pyjinhx/reactive.py:488-511` — `reported_hash = entry.get("hash")`; `fresh_hash = instance.state_hash()`; `if fresh_hash == reported_hash: continue`. This is the hash gate itself — the second gate after the dirtied-key intersection, both of which must open before bytes go over the wire (architecture-overview.md:160-162).
- `pyjinhx/cache.py:35-238` (`LoadCache`) — `install_cached_load` memoizes `load()` per `(class, load_arg)`; `_cache_get`/`_cache_put` read/write per-scope stores; `invalidate(dirtied, propagate=True)` evicts by reactive key; `_indexed_keys`/`_reverse` is the reverse index from reactive key to cache key used for eviction; `CacheScope` (`REQUEST`/`PROCESS`/`NONE`) governs whether a `ContextVar`-backed request store, a process-wide store, or no memoization backs `load()`. This is the cache-keying surface.
- `pyjinhx/keys.py` — `coerce_reactive_key`/`coerce_reactive_keys` normalize `MutationKey`/`str` to plain strings; `coerce_load_key_str` does the same but passes `None` through; `reactive_key(key, arg)` builds a per-instance dynamic key (`f"{key}:{arg}"`, wrapped as `DynamicReactiveKey`). These are the composite/parametric key coercion helpers both hash-input and cache-key questions route through.
- ADR 0009 — request-scoped `ContextVar` map, composite key (`name + id`) → instance/cached render; "layer 2 builds only what this enumeration demands."
- architecture-overview.md Invariant 1 — never re-derive structure by re-parsing rendered HTML: hash/cache lookups must not require re-parsing.
- architecture-overview.md Invariant 4 — only per-request mutable state is `ContextVar` (instance registry + RenderSession + dirtied keys + LoadCache store), reset by `request_scope`.
- architecture-overview.md:160-162 — three collaborating, distinct-question mechanisms: registry (resolve), LoadCache (does `load()` need to re-run, keyed by dirtied `react` keys), hash gate (did output actually change); both gates must open for bytes to go over the wire.
- implementation-overview.md T2:104-124 — fan-out per manifest entry `{id, type, load, hash}`: clean keys resolve via registry/LoadCache with no re-render; dirty keys re-run `load()` (cache evicted); gone keys raise `LookupError`/produce a delete; hash gate drops the swap when fresh hash equals manifest hash.

## Requirements

R1. Manifest entry shape. Each mounted region reports exactly `{type, id, load, hash}` — component type name, mounted instance id, an optional parametric load key (`None` for unkeyed singletons), and the hash it last rendered with. Mirrors `MountedManifest.parse` (`client.py:140-165`, called at `reactive.py:443`) and `_manifest_load_arg` (`reactive.py:421-425`).

R2. Manifest-to-candidate filter is two independent predicates, both must pass. (a) Class must resolve from `type` and be reactive; unkeyed regions ignore any `load`, keyed regions require it. (b) The union of the class's static react keys and (for keyed instances) its derived per-key reactive keys must intersect the request's dirtied-key set. Neither predicate alone decides whether a region gets rendered — mirrors `reactive.py:455-481`.

R3. Dedup by `(type, load_arg)`. A manifest may list the same logical instance more than once (e.g. duplicated in markup); the fan-out set is deduplicated by composite `(component_type, load_arg)` before any load/hash work runs. Mirrors `reactive.py:483-486`.

R4. Hash-input composition. The hash a component's state produces must be: (a) stable across renders for unchanged state, (b) sensitive to every state-hash-relevant field, (c) computed without re-parsing rendered HTML (Invariant 1), and (d) able to exclude fields that should not gate swaps (v0.x defaults to excluding `id`). v2 must specify the equivalent of `state_hash_exclude` and the canonicalization scheme (sorted-key JSON + SHA-256, or an equivalent stable digest) so hash comparisons are deterministic across processes/workers.

R5. Hash gate is a single equality comparison. Given a freshly computed hash and the manifest-reported hash for the same `{type, id}`, equality means "no swap, drop the candidate"; inequality means "swap goes out." This comparison happens only after R2/R3 have already selected the entry as a fan-out candidate — the hash gate is not a substitute for the dirtied-key filter, it is the second, independent gate (architecture-overview.md:160-162). Mirrors `reactive.py:509-511`.

R6. Cache key shape. The cache key for a `load()` memoization slot is `(component_class, load_arg)`, where `load_arg` is `None` for unkeyed components and a normalized string for keyed ones (via `coerce_load_key_str`). This is distinct from the manifest's `(type, id)` — multiple mounted ids of the same keyed component with the same `load_arg` share one cache entry. Mirrors `cache.py:106-139`.

R7. Cache scope and lifetime. Three scopes must be distinguishable: request-scoped (`ContextVar`, reset by `request_scope`; the default and the only one that satisfies Invariant 4 without extra machinery), process-scoped (shared across requests, needs propagation for multi-worker invalidation), and disabled (`load()` always re-runs). v2's minimal surface only strictly needs request scope to satisfy the L1 gate; process scope and cross-worker propagation are recorded as a v0.x capability, not a v2 requirement, unless #384 chooses to carry it forward.

R8. Cache invalidation by reactive key, not by cache key. Given a set of dirtied reactive keys, invalidation must evict every cache entry whose *component's* react keys intersect the dirtied set — not by iterating manifest entries. This requires a reverse index from reactive key to cache key(s) (`_reverse` in `cache.py:32,163-210`), because the trigger for invalidation (a dirtied key) and the unit of eviction (a `(class, load_arg)` slot) are different shapes.

R9. Keyed component's reactive keys are computed, not declared. A keyed reactive component's invalidation-relevant key set is its class-level static `react={...}` set unioned with per-key derived keys built from the class's static keys and its own `load_arg` (the `_keyed_derived_keys` shape). Both the manifest-filter (R2) and cache-eviction-index (R8) consume this same derived-key computation — it must be a single source of truth, not duplicated logic.

R10. Reactive-key normalization is one shared coercion. `MutationKey` enum members, plain strings, and per-instance dynamic keys (`reactive_key(key, arg)` → `f"{key}:{arg}"`) must all normalize through one coercion path before being compared, stored as cache-index keys, or intersected with a dirtied set. Mirrors `keys.py` (`coerce_reactive_key`, `coerce_reactive_keys`, `coerce_load_key_str`, `reactive_key`).

R11. Miss handling composes with the cache, not around it. A "gone" resolve (registry miss, #382's R3) must also be a defined outcome for LoadCache — attempting to re-run `load()` for a key whose entry no longer exists raises the same miss signal fan-out already handles; the cache must not silently return a stale cached instance for a key that no longer resolves to a mounted region.

R12. No re-parsing anywhere in this surface. Manifest parsing consumes a structured header value (`X-PJX-Mounted`), never rendered HTML body content. Hash computation consumes model state, never rendered markup. Cache lookups consume typed keys, never string-scan rendered output. This is Invariant 1 applied to all three (manifest, hash, cache) rather than just the registry half already covered by #382.

## Non-requirements

N1. No swap-selector construction, no root-span splicing, no delete-swap selector, no nesting dedup — all owned by #382, already settled.

N2. No process-wide cross-instance cache sharing as a v2 requirement. Process scope and multi-worker invalidation propagation (`InvalidationHub.publish`, called at `cache.py:86-87`, defined at `cache.py:288`) are recorded as a v0.x-only capability; carrying it into v2 is a decision for #384, not assumed here.

N3. No custom per-component hash override mechanism is mandated. v0.x's `state_hash_exclude` override point is worth preserving (R4), but a fully pluggable custom-hash-function API is not required by this enumeration — only that the default composition be specified precisely enough to implement.

N4. No template-visible cache or hash API. Same boundary as ADR 0004/#382 N1 — this surface is fan-out/reactivity-internal, never reachable from template code.

N5. No second cache keyed by manifest `{type, id}`. The registry (composite `name+id`, #382) and the LoadCache (`(class, load_arg)`, R6) are two different keyings for two different questions ("what's mounted" vs. "does load() need to rerun") and must not be merged into one map — conflating them was not a v0.x behavior and is not requested here.

## T2 per-branch mapping

| T2 branch | Manifest/hash/cache-specific need |
| --- | --- |
| clean-key resolve | R2 predicate (b) fails (no dirtied-key intersection) → entry is filtered out before load/hash work; registry (#382 R1) supplies the cached render. |
| dirty-key re-render | R2 predicate (b) passes → R3 dedup → `load()` reruns; R8 must have evicted the relevant cache slot when the key was dirtied, or the rerun would return stale cached state. |
| gone/LookupError-delete | R11: cache and manifest resolution must agree an entry is gone; not a hash-gate or dedup concern. |
| hash-gate-drop | R5: fresh hash equals reported hash (R4 composition) → candidate dropped. Only reached after R2/R3 already selected the entry. |
| nesting-dedup-drop | Not this surface's concern (#382 N5 territory). |
| survivor-splice-at-root_span | Not this surface's concern (#382 R4); this surface's job ends once a fresh render + hash exist for a surviving candidate. |

## Open question for #384

Whether cache scope in v2 is a single fixed request-scope (simplest, satisfies Invariant 4 with no extra machinery) or whether v0.x's three-way `CacheScope` (request/process/none) plus cross-worker propagation is carried forward as a configurable surface. This enumeration only requires that request scope exist and satisfy R6-R8; the scope-selection API, if any, is left to #384's ADR wording and L2's implementation.
