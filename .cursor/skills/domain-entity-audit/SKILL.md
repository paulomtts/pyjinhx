---
name: domain-entity-audit
description: >-
  Audit whether classes and module names match domain concepts—entities vs algorithms,
  ABC vs hub vs value object, procedural filenames vs type names. Use when naming
  new types, reviewing package structure, or asking "what should this be called".
  Read-only report.
disable-model-invocation: true
---

# Domain entity audit

## Audit ownership

**I own:** name ↔ concept alignment, entity vs algorithm vs value object classification.

**I don't own:** file splits (→ `file-responsibility-audit`), layer placement (→ `module-placement-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Expected entity map (reactive subsystem)

| Concept | Representation | Not |
|---------|----------------|-----|
| Reactive UI unit | `ReactiveComponent` (`pyjinhx/reactive/component.py:22`) | loose functions over a plain component |
| Load DI | `PjxContext` (`pyjinhx/context.py:30`), read via `get_load_context()` (`pyjinhx/session.py:213`) | ad-hoc kwargs threaded through `load()` |
| HTTP header source | request object read at the edge in `pyjinhx/client/inject.py` | a framework adapter class inside `reactive/` |
| Load memoization | module functions `cache_get` / `cache_has` / `cache_put` / `invalidate` (`pyjinhx/reactive/cache.py`) over request-scoped session stores | a cache *class* — none exists, and none is planned |
| Dirtied keys | `dirty()` / `mutates()` (`pyjinhx/reactive/mutations.py`) writing through `add_dirtied()` / `get_dirtied()` (`pyjinhx/session.py:166,158`) | a tracker object with its own lifecycle |
| Cross-worker fan-out | **does not exist** — fan-out is in-process and request-scoped (`pyjinhx/reactive/fanout.py`) | any cross-process hub/backend; do not invent one |
| Client manifest | `MountedManifest` (`pyjinhx/client/inject.py:138`) | loose dict parsing at each call site |
| Trigger region | `TriggerManifest` (`pyjinhx/client/inject.py:168`) | ad-hoc trigger header parsing |
| Load round-trip marker | `PjxKey` (`pyjinhx/reactive/component.py:90`) | magic `{{ key }}` template injection |
| Loaded asset URLs | `LoadedAssets` (`pyjinhx/client/inject.py:108`) | a bare `frozenset[str]` built inline |
| OOB swap walk | `walk_manifest()` / `oob_swaps()` over `FanoutCandidate` (`pyjinhx/reactive/fanout.py:307,450,41`) | an `OobSwaps` class (this is an algorithm, not an entity) |
| Dev guardrails | module functions + private `_DevConfig` (`pyjinhx/dev.py:24,34`) | a public config class |

## Classification rules

- **Entity / aggregate** — identity and lifecycle (`ReactiveComponent`)
- **Value object** — parse result, no mutable identity (`MountedManifest.parse`, `TriggerManifest.parse`, `LoadedAssets.parse` outputs; `FanoutCandidate`)
- **Request-scoped module** — state lives in the session, API is free functions (`pyjinhx/reactive/cache.py`, `pyjinhx/reactive/mutations.py`, `pyjinhx/registry.py`)
- **Algorithm** — stateless transform over inputs (`oob_swaps`, `walk_manifest`, `coerce_reactive_key`)
- **Port / Protocol** — extension point (`IntegrationBackend`, `pyjinhx/integrations/base.py:35`; sole implementation `FastAPIBackend`, `pyjinhx/integrations/fastapi.py:38`)

## Flag

- **P2:** A name that implies state the object does not own (a "tracker"/"hub"/"cache" class wrapping request-scoped session state)
- **P2:** Framework name on a generic seam (`FastAPI*` outside `pyjinhx/integrations/`)
- **P3:** Internal dataclass (`_DevConfig`-style private type) imported outside its module
- **P3:** Class with no state and no extension point (should be a function)

## Process

0. Grep every symbol you are about to name in a finding against `pyjinhx/` first. If it has zero hits, the finding is wrong — the codebase, not this table, is ground truth.
1. List public classes and primary functions in scope.
2. Map each to a domain concept from the table (or document gap).
3. Check the filename matches the dominant concept: a module of request-scoped functions is named for the concern (`cache.py`, `mutations.py`, `fanout.py`); a module whose point is one type is named for it (`component.py` → `ReactiveComponent`).

## Report

Use CONVENTIONS template.
