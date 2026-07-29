# Implementation overview — pyjinhx v2

Date: 2026-07-29
Status: approved. How the mechanisms in [architecture-overview.md](./architecture-overview.md) land as code: the architecture style, the folder/file structure, and the render timelines (what fires, in what order). Input for deriving the implementation roadmap; layer specs refine per-file detail just-in-time.

## Architecture style

Flat module-per-mechanism, subpackages only for cohesive clusters (reactive, client, integrations, builtins). Matches v0.x's proven layout — the rebuild analysis indicted the composition model, never the module structure — and the "small human-looking code" north star: no package-per-layer scaffolding (layer numbers are build order, not domain vocabulary), no hexagonal ports/adapters (single delivery mechanism, single template engine — abstraction layers with one implementation are over-abstraction).

The two spines from the architecture overview become a physical dependency rule — **imports flow down, hooks flow up**:

```text
reactive/ ──imports──► session, segments, descriptor     (reads root_span, registry, hook)
session   ──imports──► descriptor                        (asset_paths)
render    ──imports──► segments, component, discovery
segments  ──imports──► (nothing internal)                ← the kernel's kernel

FORBIDDEN: anything in the render spine importing reactive/.
Touch points are the only coupling: render.py fires on_rendered (a plain
callback list on the session), exposes root_span, reads the descriptor.
```

One test asserts the import graph. Cheap, catches spine violations forever.

## Folder / file structure

```text
pyjinhx2/
├── __init__.py          public API, curated exports
├── component.py         BaseComponent (strict), OpenComponent, Slot, children inference
├── descriptor.py        ClassDescriptor: MRO walk, slot fields, asset paths — frozen at registration
├── discovery.py         .pjx walk, class registry (built-then-swap), pjx_replace, dup warning
├── props_header.py      {#def#} parsing + open-class generation
├── segments.py          RenderedLevel, ChildRef, the ONE parse, root_span, splice, serialize
├── render.py            engine loop: render(), ChildRef fill, cycle guard, on_rendered hook
├── session.py           request_scope, RenderSession, minimal instance registry
├── assets.py            INLINE/NONE, manifest, hashed filenames, all_assets()
├── context.py           PjxContext
├── config.py            setup(), PjxSettings
├── dev.py               dev mode, dependency_graph()
├── reactive/
│   ├── component.py     ReactiveComponent, load(), tag-mounted load
│   ├── keys.py          MutationKey, reactive_key
│   ├── mutations.py     @mutates, dirty()
│   ├── cache.py         LoadCache
│   ├── fanout.py        state hash, hash gating, OOB fan-out, delete swaps
│   └── response.py      ReactiveResponse, HX-Reswap, redirect adaptation
├── client/
│   ├── pjx.js
│   └── inject.py        runtime injection, manifest header parsing
├── integrations/
│   └── fastapi.py
└── builtins/            L4, mirrors v0.x layout
```

Judgment calls: `segments.py` is deliberately import-pure — the type layer everything trusts. The instance registry lives in `session.py`, not `reactive/` — storage is L2, consumer is L3, matching the map. `props_header.py` stays separate from `discovery.py` — parsing vs walking, both feed the registry.

Tests mirror the package: `tests/pyjinhx2/test_<module>.py` per module, `tests/pyjinhx2/reactive/` for the cluster, plus `test_import_graph.py` (the spine rule) and the benchmark under `scripts/`.

## Render timelines

Three timelines: registration (once per process), cold render (per page), reactive request (per mutation). Module-attributed, in firing order.

### T0 — startup (once per process)

```text
import app
 1. discovery.py    walk template dirs (.pjx) ── register classes, {#def#} → generated classes
 2. component.py    __pydantic_init_subclass__ fires per class
 3. descriptor.py     └─► freeze ClassDescriptor (MRO template walk, slot fields, asset paths, mode)
 4. discovery.py    class registry built-then-swapped ── read-only from here on
```

### T1 — cold render (per request)

```text
integrations/fastapi.py   request in
 1. session.py       request_scope enters ── fresh ContextVars: RenderSession,
    │                instance registry, dirtied keys, LoadCache store
 2. reactive/…       top-level tag-mounted? load() via LoadCache (miss → real load())
 3. render.py        render(component, session)          ◄────────────────┐
    ├─ descriptor.py   read frozen descriptor (no compute)                │
    ├─ component.py    validated fields → context; slots wrapped opaque   │
    ├─ Jinja           template.render ── own markup string, autoescape   │
    ├─ segments.py     THE parse: segments + ChildRefs + root_span;       │
    │                  single-root enforced (raise)                       │
    ├─ segments.py     root-attr stamp ── splice at root_span             │
    ├─ render.py       for each ChildRef, in document order:              │
    │                    resolve tag (discovery registry; unknown → verbatim)
    │                    instantiate (JSON coercion, auto-id) ── cycle guard
    │                    recurse ────────────────────────────────────────┘
    │                    splice result as opaque node
    └─ session.py      on_rendered fires:
                         RenderSession ── set-add descriptor.asset_paths
                         reactive only ── instance-registry write;
                                          state hash; data-pjx-id/-hash
                                          spliced at root_span
 4. segments.py      serialize ── ONE recursive join (top level only)
 5. client/inject.py pjx.js inlined (cold ⇒ no X-PJX-Mounted header)
 6. assets.py        RenderSession → deduped inline <style>/<script>
 7. session.py       request_scope exits ── ContextVars reset
```

### T2 — reactive request (mutation)

```text
integrations/fastapi.py   request in ── parse X-PJX-Mounted / X-PJX-Assets / X-PJX-Trigger
 1. session.py            request_scope enters (fresh state, as T1)
 2. app handler runs:
    ├─ reactive/mutations.py  @mutates / dirty() ── record dirtied keys
    └─ reactive/cache.py        └─► evict LoadCache entries via react={} reverse index
 3. handler returns component | ReactiveResponse
 4. render.py             primary render ── T1 steps 3-4 (pjx.js NOT re-injected)
 5. reactive/fanout.py    for each manifest entry {id, type, load, hash}:
    ├─ clean keys?   ── instance registry / LoadCache resolve ── NO re-render, NO load()
    ├─ dirty keys?   ── load() re-runs (cache was evicted) ── render (T1 steps 3-4)
    ├─ gone?         ── LookupError ── delete swap
    ├─ hash gate     ── fresh hash == manifest hash ── swap dropped
    ├─ nesting dedup ── region inside another survivor ── dropped (segment containment)
    └─ survivor      ── hx-swap-oob spliced at its root_span
 6. reactive/fanout.py    asset delta vs X-PJX-Assets ── OOB asset fragments
 7. reactive/response.py  OOB-only? ── HX-Reswap: none
 8. client/pjx.js         applies swaps ── updates its mounted map ── next manifest reflects it
```

## Load-bearing ordering facts

Facts the timelines pin down, which layer specs must not violate:

- **Root-attr stamp precedes child fill.** The parent's first segment is final early; nothing later shifts offsets within a segment, so recorded spans stay valid.
- **`on_rendered` fires depth-first post-order.** Each component's hook fires after its own subtree completes; children fired their own hooks already, so session state accumulates bottom-up.
- **Serialize and asset emission happen exactly once, at the top.** No intermediate joins anywhere in the tree.
- **Fan-out runs after the primary render and must exclude regions the primary response already contains.** Otherwise a region swaps twice (once as primary content, once OOB). v0.x handles this via nesting dedup against the primary; the L3 spec needs an explicit line for it.
