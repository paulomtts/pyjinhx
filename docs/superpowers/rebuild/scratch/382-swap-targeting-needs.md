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
