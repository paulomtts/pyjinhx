# v2 feature port list

Date: 2026-07-29
Status: approved. Decided against the full v0.36 inventory (70+ features, agent-swept from docs/guide, CHANGELOG, public API, builtins). This file owns the feature universe: per-feature verdict AND the build layer that ships it. A layer's just-in-time spec must cover every feature assigned to it. Parity checklist for PRD goal G3.

Verdicts: **keep** (ports as-is in behavior), **mod** (ports with changed shape — the change is noted), **drop** (does not exist in v2). Layer "—" = dropped, nothing ships.

## 1. Component definition

| Feature | Verdict | Layer | Notes |
|---|---|---|---|
| BaseComponent + Pydantic field validation | keep | L0 | strict core now (ADR 0006) |
| Classless components via `component()` | keep | L1 | |
| `{#def#}` prop headers | keep | L1 | built on the open opt-in subclass |
| Extra/stray fields accepted | mod | L1 | only on the open opt-in subclass, not on strict base |
| `Slot` type | mod | L1 | string slots stay raw-HTML-capable; component slots are opaque nodes |
| Children/`content` inference (single `Slot()` / `_pjx_children_target`) | keep | L1 | |
| Stale-`{#def#}` warning | keep | L1 | |
| SFC `{# python #}` blocks | **drop** | — | ADR 0008 — not deferred, not ported |

## 2. Composition

| Feature | Verdict | Layer | Notes |
|---|---|---|---|
| PascalCase tags | keep | L1 | expansion via segment model, one parse per level (ADRs 0002/0005) |
| Attribute pass-through to root | keep | L0 | stamped at recorded root span, no parse |
| JSON-string attr coercion (`list`/`dict`/`BaseModel`) | keep | L0 | at instantiation |
| Slots | mod | L1 | opaque + truthiness only; string filters raise clear error (ADR 0003) |
| Direct nesting (instances as field values) | keep | L1 | |
| Lists & dicts of components | keep | L1 | |
| NestedComponentWrapper (`{{ field.props.x }}`, `{{ field }}`) | keep | L1 | both work on opaque nodes |
| Single-root invariant | mod | L0 | stricter — violations raise, no silent-stamp fallback |
| Auto-generated `pjx-<n>` IDs, `auto_id=False` | keep | L0 | |

## 3. Discovery & registration

| Feature | Verdict | Layer | Notes |
|---|---|---|---|
| Class registry | keep | L2 | |
| Instance registry | mod | L2 | minimal, reactivity-only: maps name+id to instance/cached render for OOB fan-out and not-dirtied cache hits. No template-visible cross-reference (ADRs 0004/0009) |
| Request scoping (`request_scope`) | keep | L2 | |
| Composite keys (name + id) | keep | L2 | |
| Template autodiscovery | mod | L1 | `.pjx` + snake_case only (ADR 0007); `.html`/`.jinja` and kebab probing dropped |
| MRO template/asset resolution | keep | L0 | nearest-ancestor per kind, frozen into the descriptor at registration (ADR 0010) |
| Duplicate-class warning | keep | L1 | |
| `pjx_replace=True` shadowing | keep | L1 | |

## 4. Rendering & context

| Feature | Verdict | Layer | Notes |
|---|---|---|---|
| Renderer + Jinja environment | keep | L0 | |
| Default-environment project-root detection | keep | L0 | |
| Autoescape on, escape-by-default + Slot exemption | keep | L0 | invariant 6 |
| Root-attr stamping (override semantics) | mod | L0 | offset splice at recorded span; no document parse |
| PjxContext injection (`load()` param / `PjxContext.current()`) | keep | L3 | |
| Render cycle guard | mod | L1 | cross-ref gone, so cycles only via nesting/`load()` chains; simpler guard |
| Opaque-slot placeholder machinery | **drop** | — | segment model makes it unnecessary (ADR 0002) |
| Resolution memoization caches | **drop** | — | replaced by the per-class descriptor (invariant 5) |
| Post-hoc thread-safety patches | **drop** | — | replaced by invariant 4 (built-then-swap or ContextVar) |
| Registry cross-reference in templates | **drop** | — | ADR 0004 |

## 5. Assets — all keep, ship in L2

Co-located `.js`/`.css` discovery, INLINE/NONE modes, per-session dedup, nested aggregation, `asset_manifest()`, `pjx.js` runtime injection (skip when `X-PJX-Mounted`), hashed filenames + `resolver_with_hash()`, `Finder.all_assets()`, extra `js=[]`/`css=[]` fields. (OOB/head-channel asset *delivery* ships with L3 — it needs fan-out.)

## 6. Reactivity & HTMX — all keep, ship in L3

ADR 0001 parity: ReactiveComponent + `load()`, MutationKey, `@mutates`, `dirty()`, OOB swaps, per-request load cache, instance-keyed components (`PjxKey`), `reactive_key` parametric keys, state hashing + hash gating, delete swaps on `LookupError`, client manifest headers (`X-PJX-Mounted`/`X-PJX-Assets`/`X-PJX-Trigger`), ReactiveResponse, tag-mounted `load()`, loading indicators, `HX-Reswap: none` emission, htmx redirect adaptation. Also L3: `setup()` middleware + PjxSettings, FastAPI integration, reactive dev mode, `dependency_graph()`, unconsumed-mutation check — they only earn their keep once reactivity exists.

| Feature | Verdict | Layer | Notes |
|---|---|---|---|
| Nesting dedup of OOB swaps | mod | L3 | segment tree knows containment structurally; v0.x heuristic replaced |
| Cross-request InvalidationBackend (Redis/SQLite) | defer | post-1.0 | ADR 0011; per-request load cache ships in L3 |

## 7. Builtins — port all, ship in L4

All 60+ components (ADR 0011 context). Families: icons/display (Icon, Badge, Avatar/Stack, Divider, Progress, Spinner, Skeleton, EmptyState), navigation (Breadcrumb, TabGroup/List/Tab/Panel, Paginator), data (Table family), forms (Button, ChipInput, FormField, PasswordInput, SegmentedControl, ToggleSwitch), dialogs/overlays (Modal, Drawer, ConfirmDialog, PromptDialog, Popover families), Dropdown, Accordion family, lazy/loading (LazyLoad, RegionLoader, PageLoader), notifications (Notification, ToastHost), Alert, helpers (Card, Tooltip, Resizable, Carousel families). Already-removed stay dead: PJXPanel, PJXLazyPanel.

## 8. Dev tooling & misc

| Feature | Verdict | Layer | Notes |
|---|---|---|---|
| Scaling benchmark | keep | L0 | invariant 8 — exists before L1 |
| Reactive dev mode (warn/strict) | keep | L3 | |
| `dependency_graph()` / mermaid formatting | keep | L3 | |
| Unconsumed-mutation check | keep | L3 | |
| `setup()` middleware + PjxSettings | keep | L3 | |
| FastAPI integration | keep | L3 | |
| Public `Parser`/`Tag` parse-tree API | **drop** | — | v2 exposes segment-model types instead; no compat shim (ADR 0011) |
| pjx-ls (LSP) | out of scope | post-1.0 | needs a v2 pass eventually; not part of this blueprint |

## Placement rationale

Two judgment calls, decided 2026-07-29:

1. **`{#def#}` headers and classless `component()` sit in L1, not L0.** They depend on discovery and the open opt-in subclass, not on composition itself — but L0's done-criteria stay minimal (one class-based component renders), and discovery ships with L1's tag resolution anyway. L0 stays the smallest shippable kernel.
2. **`setup()`, FastAPI integration, and dev tooling sit in L3.** They only earn their keep once reactivity exists — before that, nothing needs middleware, client headers, or a dependency graph.

MRO resolution lands in L0 because it lives inside the descriptor computation (per-class, at registration), even though its main consumer is subclassing builtins in L4.
