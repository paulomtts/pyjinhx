# Implementation roadmap — pyjinhx v2

Date: 2026-07-29
Status: approved, living — check items off as they ship. Derived from [feature-port-list.md](./feature-port-list.md) (what each layer must cover), [implementation-overview.md](./implementation-overview.md) (files + timelines), [architecture-overview.md](./architecture-overview.md) (ship criteria), and the PRD's gating goals. Each layer runs as one /feature cycle (spec → adversarial review → plan → implement → test-integrity gate); inner steps are the intended PR-sized units, in dependency order. A layer's spec may reorder inner steps with reason, but may not weaken its deliverable.

```text
L0 kernel ──► L1 composition ──► L2 registry+assets ──► L3 reactivity ──► L4 builtins ──► 1.0
        gate:                gate:
        slot-filter          instance-registry
        survey (ADR 0003)    enumeration (ADR 0009)
```

---

## L0 — kernel · [milestone #1](https://github.com/paulomtts/pyjinhx/milestone/1)

**Deliverable:** `render(Card(title="x"))` returns finished HTML — strict validation, root attrs stamped at the recorded span, single-root violations raise, benchmark exists with baseline recorded. The smallest thing that proves the segment model.

Inner order (each step testable before the next starts):

- [x] **1. `segments.py`** ([#244](https://github.com/paulomtts/pyjinhx/issues/244)) — `RenderedLevel`, `ChildRef`, the one parse (segment cuts + root_span + single-root), splice, serialize. Import-pure, all pure functions: build and test it against raw strings before any component exists.
- [x] **2. `component.py`** ([#245](https://github.com/paulomtts/pyjinhx/issues/245)) — strict `BaseComponent`, `Slot` type, auto-`pjx-<n>` IDs, JSON-string attr coercion. No rendering yet; pure model behavior.
- [x] **3. `descriptor.py`** ([#246](https://github.com/paulomtts/pyjinhx/issues/246)) — `ClassDescriptor` frozen in `__pydantic_init_subclass__`: single-probe template resolution (`.pjx` + snake_case), MRO walk per kind with provenance, slot-field set, asset paths, strict/open mode flag.
- [x] **4. `render.py` (single level)** ([#247](https://github.com/paulomtts/pyjinhx/issues/247)) — Jinja environment (autoescape on, default-env project-root detection), context build from validated fields, `template.render` → the one parse → root-attr stamp → serialize. T1 steps 3-4 for a childless component.
- [x] **5. Guards + bench** ([#248](https://github.com/paulomtts/pyjinhx/issues/248)) — `test_import_graph.py` (spine rule live from day one), `scripts/bench_render_scaling_v2.py`, baseline number recorded in this file.

Baseline (2026-07-30, `uv run python scripts/bench_render_scaling_v2.py`, N childless components):

```
n=  50       1.0 ms    0.02 ms/component
n= 100       1.8 ms    0.02 ms/component
n= 200       3.7 ms    0.02 ms/component
n= 438       7.9 ms    0.02 ms/component
```

**Gate before L1** ([#249](https://github.com/paulomtts/pyjinhx/issues/249)) — ✅ **passed, 2026-07-30.** Slot-filter survey (#293 builtins, #294 docs+demos) found zero occurrences of string filters/slicing/membership/comparisons on component-slot values. #295 classified this as rare-path; #296 recorded the rare-path outcome — error contract and migration note — directly in [ADR 0003](adr/0003-slot-opacity.md#survey-outcome-2026-07-30). #297 (widespread-path) closed not-applicable. ADR 0003's decision (opaque + truthiness/interpolation only) stands unchanged; L1's RFC can proceed against the recorded error contract with no further mitigation needed.

---

## L1 — composition · [milestone #2](https://github.com/paulomtts/pyjinhx/milestone/2)

**Deliverable:** a builtin-shaped nested page renders — component trees, generated tags, classless components — with the benchmark showing linear scaling (PRD G1 evidence starts here).

- [ ] **1. `discovery.py`** — `.pjx` walk, class registry (built-then-swap), duplicate warning, `pjx_replace`.
- [ ] **2. ChildRef fill in `render.py`** — resolve tag against registry (unknown → verbatim passthrough), instantiate with coerced attrs, recurse, splice opaque node, cycle guard. This is the step that turns T1's loop real.
- [ ] **3. Slots & children** — opaque-node semantics (truthiness + interpolation; string filters raise the clear error), children/`content` inference, direct nesting, lists & dicts, `NestedComponentWrapper` (`{{ field.props.x }}` / `{{ field }}`).
- [ ] **4. Classless surface** — open opt-in subclass, `props_header.py` ({#def#} parse + class generation, stale-header warning), `component()`.
- [ ] **5. Scaling proof** — bench sweep to 10k components; ms/component flat. Record the number.

Linear-scaling number: _(record here)_

**Gate before L2:** instance-registry enumeration — list exactly what reactivity needs from it (swap targeting, manifest membership, hash inputs, cache keying) per ADR 0009. L2 builds only what's listed.

---

## L2 — registry + assets · [milestone #3](https://github.com/paulomtts/pyjinhx/milestone/3)

**Deliverable:** full static pages with correct deduped assets, safe under concurrent requests (PRD G6 tests land here and stay in CI).

- [ ] **1. `session.py`** — `request_scope` ContextVars (session, instance registry, dirtied-keys store, cache store — all reset on exit), `on_rendered` hook plumbing from `render.py`.
- [ ] **2. `assets.py`** — accumulation off descriptors, per-session dedup, INLINE/NONE emission at top-level serialize, `asset_manifest()`, hashed filenames + `resolver_with_hash()`, `all_assets()`.
- [ ] **3. Instance registry (minimal)** — exactly the enumerated surface from the L2 gate; composite keys; written only by reactive paths (stub-consumed until L3).
- [ ] **4. Concurrency tests** — FastAPI-threadpool-shaped test: parallel renders, no state bleed, no `FileNotFoundError`-class races. The invariant-4 census gets asserted here.

---

## L3 — reactivity · [milestone #4](https://github.com/paulomtts/pyjinhx/milestone/4)

**Deliverable:** reactive behavior parity — a mutation round-trip demo (dirty → evict → fan-out → gated OOB swaps → swap-in assets) plus the ported v0.x reactive test suite green (PRD G4).

- [ ] **1. `reactive/keys.py` + `mutations.py`** — MutationKey, `reactive_key(key, arg)`, `@mutates`, `dirty()`; dirtied-keys request state.
- [ ] **2. `reactive/cache.py`** — LoadCache: `(class, key)` memoization, `react={}` reverse index, eviction by dirtied keys.
- [ ] **3. `reactive/component.py`** — ReactiveComponent, `load()` wrap at class-definition time, tag-mounted `load()`, instance-keyed components (`PjxKey`).
- [ ] **4. State hash + stamping** — SHA-256 over sorted `model_dump()` minus exclusions; `data-pjx-id`/`data-pjx-hash` spliced at root_span via the `on_rendered` reactive branch; instance-registry writes go live.
- [ ] **5. `reactive/fanout.py`** — manifest walk, clean/dirty resolution (cached render vs re-`load()`), hash gate, structural nesting dedup, primary-region exclusion (the T2 ordering fact), delete swaps on `LookupError`, `hx-swap-oob` splice.
- [ ] **6. `reactive/response.py`** — ReactiveResponse, `HX-Reswap: none`, htmx redirect adaptation.
- [ ] **7. `client/`** — port `pjx.js` (manifest scan, swap apply, loading indicators, toast/loader APIs, vendored htmx), `inject.py` cold-render injection + header parsing.
- [ ] **8. Wiring** — `config.py` (`setup()`, PjxSettings), `integrations/fastapi.py`, `context.py` (PjxContext), `dev.py` (dev mode, `dependency_graph()`, unconsumed-mutation check).
- [ ] **9. Parity suite** — port the v0.x reactive test suite; green = layer done.

---

## L4 — builtins · [milestone #5](https://github.com/paulomtts/pyjinhx/milestone/5)

**Deliverable:** 1.0 readiness — all builtins green under v2, benchmark comparison v0.36 vs v2 published (PRD G2), migration guide shipped (G5), package renamed and released as pyjinhx 1.0.

Port order — dependency- and risk-sorted, tests ported alongside each family:

- [ ] **1. Display primitives** — Icon, Badge, Avatar/Stack, Divider, Progress, Spinner, Skeleton, EmptyState. Simplest; smoke-tests L1's classless + slot semantics in volume.
- [ ] **2. Forms** — Button, ChipInput, FormField, PasswordInput, SegmentedControl, ToggleSwitch.
- [ ] **3. Composed shells** — Card, Modal, Drawer, Accordion, Tabs, Popover, Tooltip, Dropdown, Breadcrumb families. Heaviest users of slots/children composition and MRO subclassing.
- [ ] **4. Data + HTMX-heavy** — Table family, Paginator, LazyLoad (+ infinite-scroll sentinel), RegionLoader, PageLoader. Exercises reactivity + loading indicators hard.
- [ ] **5. JS-heavy tail** — Notification, ToastHost, Alert, Carousel, Resizable families.
- [ ] **6. Release train** — bench comparison on the builtin-heavy page (G2: never slower), migration guide written from the port list's mods/drops (G5), rename `pyjinhx2` → `pyjinhx`, publish 1.0, freeze v0.x to critical fixes.

Bench comparison: _(record here)_

---

## Post-1.0 backlog

- Cross-request InvalidationBackend port (Redis/SQLite) — ADR 0011.
- pjx-ls v2 pass (drops `{# python #}` support per ADR 0008).
- v0.x features shipped after 0.36.4, triaged from the PRD's pinned-baseline risk.
