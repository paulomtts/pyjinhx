# pyjinhx runtime decision trees

What the library decides, in the order it decides it. Traced from source
against `2ded3808`, covering the request round-trip, the render core, the two
cache tiers, and the reactive fan-out.

pyjinhx turns *one handler return value* into *one HTTP response*. A component
is a Pydantic model plus a Jinja template sitting next to it. The library's
whole job is: render that thing, and — if it's reactive — figure out what
*else* on the user's page just went stale and ship patches for those regions
too, in the same response.

Everything below is that sentence expanded.

Companion to [architecture-overview.md](./architecture-overview.md), which maps
how the mechanisms *interact*; this one walks the branch points inside them.

---

## Top level: what a request becomes

```text
  browser (htmx)                                            server
      │  POST /todos/toggle                                    │
      │  + X-PJX-Mounted   ("here's what's on my page")         │
      │  + X-PJX-Assets    ("here's the CSS/JS I already have") │
      └────────────────────────────────────────────────────────►│
                                                     PjxScopeMiddleware
                                                   opens request_scope()
                                                (ContextVars: registry,
                                                 caches, dirtied set…)
                                                            │
                                                       your handler
                                                    (@mutates marks
                                                     state keys dirty)
                                                            │
                                                       compose(result)
                                                            │
                                    ┌───────────────────────┴──────────┐
                                    ▼                                  ▼
                            render the primary                    fan out
                          (the thing you returned)         (everything else on
                                    │                        the page that went
                                    │                          stale)
                                    └───────────────┬──────────────────┘
                                                    ▼
                                    body = primary + OOB swaps + assets
      ◄─────────────────────────────────────────────┘
```

---

## 1. `compose()` — is this even mine?

`pyjinhx/responses.py`

```text
handler returned …
├── a BaseComponent ──────────► render it → primary
├── None ─────────────────────► primary = ""      (OOB-only response)
├── a str / has __html__ ─────► wrap in Markup → primary
└── anything else ────────────► PASSTHROUGH — not pyjinhx's, hand it back
                                (this is how your redirects survive)

then, on every path that produced a body:
    invalidate(dirtied)   ← evict caches BEFORE walking, never after
    fan out
    primary empty? ──yes──► header HX-Reswap: none  (or htmx wipes the trigger)
```

---

## 2. `render_level()` — rendering one component

`pyjinhx/rendering.py`

This is the recursive core. Static and reactive, primary and OOB —
**everything** funnels through here. There is no second renderer.

```text
render_level(component)
│
├─ cycle guard: same class 32 times on ONE path? ──► raise ValueError
│     (Card > Row > Card is perfectly fine, and so is 31 of them — what
│      trips it is a path that never terminates, i.e. Card > Card > Card…)
│
├─ TIER-2 RENDER CACHE — eligible?
│   ├─ is it reactive (has _pjx_key_field)? ──yes──► OFF
│   │     (reactive caches its load() instead; caching both would key one
│   │      component against two independently-invalidated stores)
│   ├─ measured cheaper to render than to cache? ──yes──► OFF
│   ├─ holds a component in a slot/children field? ──yes──► OFF
│   │     (slot tokens are only valid for the one template.render() call)
│   └─ still on? ──► look up
│         ├─ HIT ──► _finish_cached_level() ── RETURN, template never runs
│         └─ MISS ─► fall through ↓
│
├─ build context  (model_dump + slots)
├─ Jinja render   (autoescape ON)
├─ ONE parse      (VerbatimParser) → segments + root_span
├─ single-root rule: 0 or 2+ roots? ──► raise ValueError
├─ maybe save to render cache (only if no auto-generated id leaked into output)
│
├─ FILL CHILDREN — each <PascalCase/> tag is a hole:
│     ├─ unknown tag ──────────► stays literal text, hole closes
│     ├─ plain component ──────► constructor
│     └─ reactive component ───► its cache-routed load()   ─┐
│         then ── recurse into render_level ────────────────┘
│         (children enter as whole objects, never text spliced into text —
│          that's what keeps a child's markup un-reparsed and un-escaped)
│
├─ splice slot nodes
└─ emit_rendered(component, level)   ← fires LAST, bottom-up
      subscribers: stamp data-pjx-* attrs · accumulate CSS/JS · register instance
```

---

## 3. `load()` — the two cache tiers

`pyjinhx/reactive/component.py`, `pyjinhx/reactive/cache.py`

Every reactive class's `load()` is silently wrapped at class-definition time.
Both the primary render and every OOB region go through this same wrapper.

```text
load(key)
│
├─ TIER 1 (request-scoped dict) hit? ──yes──► RETURN
│
├─ derive react keys:  ("todos",)  +  ("todos:1",) if this call has a load key
│     both forms, because @mutates(key=...) dirties only the composite
│
├─ TIER 2 (cross-request: disk/redis/sqlite) configured?
│     ├─ backend degraded (a previous evict() raised)? ──► skip reads
│     ├─ get() raised? ──► note failure, treat as miss   (a cache never errors a request)
│     └─ HIT ──► promote into tier 1 ──► RETURN
│
├─ call your real load()
├─ returned wrong type? ──► TypeError
├─ put into tier 1 (reverse-indexed by react keys)
└─ put into tier 2 (same keys become the backend's tags, + ttl)
```

---

## 4. Fan-out — what else on the page is stale?

`pyjinhx/reactive/fanout.py`

Three passes, deliberately not one loop.

```text
X-PJX-Mounted = [{id, type, load, hash}, …]   ← what the browser says it's showing

FILTER PASS (all the cheap checks, no I/O)
  for each mounted region:
    ├─ already inside the primary body?  ──► skip (else it'd swap twice)
    ├─ unknown tag?                      ──► skip
    ├─ no dirtied key touches its class? ──► skip
    ├─ duplicate (type, load-key)?       ──► skip (one load per pair)
    └─ keep → clean = "is it still in the load cache?"

BUILD PASS (the only expensive part)
    every pending class measured as cheaper-than-a-thread?
      ├─ yes ──► run inline on this thread
      └─ no  ──► ThreadPoolExecutor, each build in copy_context()
                 (a bare thread would see empty ContextVars and write
                  its caches into a throwaway dict)

REDUCE PASS — assign each survivor a status
    ├─ was clean            ──► "clean"    → emits NOTHING
    ├─ load() raised LookupError ──► "missing" → <div hx-swap-oob="delete:…">
    ├─ re-rendered, hash unchanged ──► DROP (keys changed, output didn't)
    └─ otherwise            ──► "dirty"   → outerHTML swap
    then: nested inside another survivor's region? ──► DROP (parent carries it)

OOB_SWAPS — stamp and serialize
    for each dirty region:
      stamp hx-swap-oob + data-pjx-hash onto the root tag (one splice, no re-parse)
      walk it for nested reactive regions this request did NOT dirty
        └─► stamp hx-preserve="true" so the parent's swap lands *around* them
```

---

## The notes that matter

- **The ContextVar spine is the real architecture.** `request_scope()` is a
  single context manager that opens the instance registry, both cache tiers,
  the dirtied set, and the load context. Nothing is passed as a parameter — it
  is all read from ContextVars. Clean and non-duplicated, but *invisible*: code
  that runs outside a request scope silently gets defaults instead of failing,
  which is exactly why the fan-out has to copy the context into every worker
  thread.

- **`ReactiveComponent` is a subclass, not a parallel system.** Reactivity is
  caching + stamping + fan-out bolted onto the one render path. That is the
  single biggest thing keeping this codebase from having two of everything.

- **Four tiers of adoption, and you can stop at any of them:** components alone
  (no framework) → request scoping → reactive HTMX → full wiring (context
  factory, cache backends, dev warnings). Tier 1 does not even need a web
  server. See [usage-tiers.md](../../guide/usage-tiers.md).

- **The nesting blind spot sits in two places on these trees** — the "nested
  inside another survivor?" line in the reduce pass (#1027's wasted work), and
  the tier-2 box in tree 3 (#1026's stale replay). Neither box knows the
  containment relation up front; both discover it, or fail to, after the fact.
