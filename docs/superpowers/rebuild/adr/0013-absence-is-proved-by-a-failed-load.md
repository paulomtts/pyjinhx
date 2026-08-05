# ADR 0013: Absence is proved by a failed load, not by a registry miss

**Status:** Accepted, 2026-08-04. Amends ADR 0009 (E1, E17) and depends on ADR 0012. Recorded as a new ADR rather than an edit, per the immutability rule in this directory's README.

## Context

ADR 0009 gave the instance registry three properties that turn out to interact badly. **E6** makes its storage request-scoped, reset by `request_scope`. **E7** makes the Load path its single writer, with OOB fan-out a read-only consumer. **E1** requires a composite key to resolve to a live instance, a cached `RenderedLevel`, *or a miss* — and **E4** requires that miss be observably distinguishable at the call site from a single lookup.

The L3.5 implementation read that miss as evidence of absence:

```python
resolved, found = _resolve_registry_entry(cls, instance_id)
if not found:
    status = "missing"  # -> <div hx-swap-oob="delete:[data-pjx-id='...']">
```

Compose E6 and E7 and that reading collapses. In production the registry is written only by `register_rendered_instance`, subscribed to `on_rendered`, so it contains exactly the regions the *current* request rendered. A T2 request renders its primary and nothing else. Every region outside the primary tree — which is precisely the set fan-out exists to refresh — therefore misses the registry as a matter of course.

The check also ran ahead of the cache check and ahead of `_build_dirty`, so the dirty path was unreachable for those regions. The observable result, once ADR 0012 made fan-out unconditional and the `data-pjx-type` stamping gap was closed, was that toggling one row of the todo example deleted the counter, the total and the clear button from the DOM instead of refreshing them.

This was latent for as long as fan-out was opt-in and the walk was filtering everything out earlier for unrelated reasons. It is not a regression introduced by ADR 0012; ADR 0012 is what made it observable.

## Options

1. **Pre-populate the registry from the manifest before the walk.** Rejected: circular. The manifest is the client's claim about what is mounted; seeding the registry from it and then asking the registry what is mounted answers the question with its own input, and it would put a second writer on the registry in violation of E7.
2. **Make the registry process-scoped.** Rejected: E6 is deliberate, N6 explicitly rules out a process-wide cache as a mandate, and cross-request instance identity would reintroduce exactly the shared mutable state the request scope exists to prevent.
3. **Keep the gate, and let a dirty rebuild fall back when the registry misses.** Rejected as incoherent: it retains a check whose answer is "miss" on the overwhelmingly common path, so the check earns nothing and only obscures where the decision is really made.
4. **Demote the registry from gate to hint; let a failed `load()` prove absence.** Chosen.

## Decision

Option 4.

**A registry miss carries no information about existence.** `_resolve_registry_entry` is still called, and what it returns is still used — on the clean path it supplies the already-rendered `RenderedLevel` that lets a cache hit skip re-rendering. But it no longer decides anything. E1's three-way resolve and E4's distinguishable miss both stand as stated; what changes is only the *inference* a consumer is entitled to draw from a miss, which ADR 0009 never actually licensed.

**A `LookupError` raised out of `load()` is the sole evidence that a region no longer exists.** `_build_dirty` catches it and marks the candidate `"missing"`; `oob_swaps` renders that as the delete swap. This is the honest test, because it asks the only component that knows — the one that owns the data.

**E7 is preserved.** Fan-out still never writes the registry. `cls.load()` writes the *load cache*, through the L3.2 memo wrap, which is a different key space (E13) and was already the dirty path's behaviour.

**E17 is better served, not weakened.** "A key that no longer resolves must not yield a stale cached instance or render" is satisfied more strongly by a fresh rebuild than by a delete: the region ends up showing current data rather than being removed on the strength of a lookup that was never about existence.

## Consequences

- **Raising becomes part of `load()`'s public contract.** A component reports "this instance is gone" by letting `LookupError` out — and since `KeyError` and `IndexError` subclass it, an ordinary dict or list lookup against the app's own store is already the correct signal, with no pyjinhx-specific exception type to learn.
- **Correspondingly, swallowing is now a bug with a visible symptom.** A `load()` that catches its store's `KeyError` and returns a field-default instance suppresses the signal, and its region is swapped with a blank render rather than deleted. The todo example did exactly this and had to be fixed. `docs/reactivity.md` had documented the raise-to-delete behaviour correctly all along; the implementation and the example were the parts that diverged.
- **A missing region costs one failed `load()`** where it previously cost none. Accepted: it is the rare path, and it is the price of asking a question that can actually be answered.
- **Eleven unit tests changed shape.** They expressed "gone" as an id absent from the registry; they now express it as a `load()` that refuses. That the old tests passed against a walk which, in production, deleted every region it touched is itself the lesson — the fixture seeded the registry by hand, so the tests never exercised the configuration real requests are always in.
- **The delete path is now reachable only through app code.** If an application's every `load()` swallows its lookup errors, that application will never emit a delete swap. This is a deliberate trade: the framework cannot distinguish "gone" from "empty" without the app telling it, and guessing from a request-scoped registry is what this ADR exists to stop.
