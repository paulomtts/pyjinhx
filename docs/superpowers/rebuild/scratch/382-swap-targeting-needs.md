# L1.G.1 — swap-targeting needs from the L2 instance registry

Input to #384 (record enumeration in ADR 0009). Analysis only: no code, no ADR edit, no roadmap edit. Companion half is #383 (manifest membership, hash inputs, cache keying) — deliberately absent here.

This document answers exactly one question: what must the request-scoped instance registry expose so OOB fan-out can target swaps? Anything not listed here is not built (ADR 0009: "anything it doesn't list doesn't get built").

## Source grounding

- `pyjinhx/reactive.py:447` — v0.x resolves the component class via `Registry.get_classes()[type]`, then at `pyjinhx/reactive.py:493,495` calls `component_class.load(load_arg)` or `component_class.load()`. This is the composite-key resolve v2 must keep. (Observed line numbers drifted from the spec's citation of `reactive.py:464,491-495`; using the observed numbers here.)
- `pyjinhx/reactive.py:411-413` — v0.x builds the OOB swap selector (`_oob_swap_selector`) from the region's `data-pjx-id`; `_oob_delete_selector` (line 416) builds the delete-swap selector. Only outerHTML and delete exist (ADR 0001).
- `pyjinhx/reactive.py:496` — `except LookupError:` is the delete-swap path: the region is gone, so fan-out emits a delete candidate rather than a render.
- `pyjinhx/reactive.py:388-408` — `_drop_nested` scans candidate HTML strings for containment (`data-pjx-id="..."` marker substring) to drop nested candidates. v2 does not need this: the segment tree already knows containment structurally.
- `pyjinhx/reactive.py:523` — `_extra_root_attrs` is passed into `instance._render(...)` to splice `hx-swap-oob` and `data-pjx-hash` into the root tag at render time, i.e. an implicit string-level relocation/injection at the root. v2 records a `root_span` at render time instead (architecture-overview.md: "Root span is written twice, parsed never").
- ADR 0001 — outerHTML-only swaps; no delta, no append/prepend.
- ADR 0009:13-24 — Option 3: request-scoped ContextVar map, composite key (`name + id`) -> instance/cached render, used exclusively by OOB fan-out and load-cache lookups, not template-visible; the pre-RFC-2 enumeration is the gate.
- architecture-overview.md Invariant 1 — never re-derive structure by re-parsing rendered HTML.
- architecture-overview.md Invariant 4 — registry storage is per-request ContextVar state reset by `request_scope`; not process-wide, not built-then-swap.

## Registry requirements (swap targeting only)

R1. Composite-key resolve. Given `{type, id}` from a mounted region, one lookup returns either a live instance, or a cached `RenderedLevel` carrying its `root_span`, or a miss. Mirrors `reactive.py:447,493,495`, except v2 routes to a recorded `root_span` instead of re-deriving one.

R2. Swap-target identity. The resolved entry must carry enough identity to name a stable `data-pjx-id`-equivalent selector target and to splice at the recorded `root_span`. outerHTML only (ADR 0001; `reactive.py:411-413`). No delta, append, or prepend machinery.

R3. Observable miss. The lookup distinguishes "gone" (drives a delete swap) from "present-but-clean" (drives skip). That distinction must be readable by fan-out from the lookup result alone — never by re-parsing HTML or by a second pass. v0.x expressed "gone" as `LookupError` (`reactive.py:496`).

R4. Root-span routing, not root relocation. For a resolved key the registry hands back the already-recorded `root_span`. It must never trigger, require, or imply a re-parse or string scan of rendered HTML to find a root tag (Invariant 1). This replaces v0.x's implicit `_extra_root_attrs` splice (`reactive.py:523`).

R5. No containment/nesting API. Fan-out's nesting dedup is served by the segment tree's structural containment, not by registry state. Recorded here as a deliberate non-requirement so L2 does not port `_drop_nested` (`reactive.py:388-408`) into the registry.

R6. Storage and lifetime. A request-scoped `ContextVar` map from composite key (`name + id`) to instance/cached render, reset by `request_scope`. Not process-wide, not built-then-swapped (Invariant 4; ADR 0009:13-17).

R7. Consumer boundary. The registry is written only by Load (single-writer, thick edge in architecture-overview.md: "`Load` is the only writer of `InstReg` entries") and read-only from fan-out's perspective — the `InstReg -> Fanout` edge in architecture-overview.md's mermaid map is a solid labeled edge ("resolve name+id; cached render if clean"), not dotted (verified against the map's own edge-semantics legend: solid = consumer cannot produce output without this input, dotted = keyed lookup/hook whose miss is a defined non-error path). Fan-out never mutates the registry, and no third writer exists.

## Non-requirements

Recorded so L2 does not over-build. Each is a thing the registry explicitly does not do.

N1. No template-visible lookups. Templates cannot reach the registry; peer cross-reference died with ADR 0004.

N2. No append/prepend/delta swap modes. outerHTML swaps plus delete swaps are the entire surface (ADR 0001).

N3. No second HTML parse and no string search to relocate roots. The recorded `root_span` is the only route to a splice point (Invariant 1).

N4. No manifest-hash comparison, no hash-input composition, no cache-keying scheme. This document names only the clean / dirty / miss branches that need *a* lookup; how cleanliness is decided is #383's half.

N5. No registry state for nesting dedup. Structural containment lives in `segments.py` (see R5).
