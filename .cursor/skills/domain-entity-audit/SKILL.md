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
| Reactive UI unit | `ReactiveComponent` | functions in `component.py` only |
| Load DI | `LoadContext` | `get_load_context()` wrapper |
| HTTP header source | `ClientBackend` ABC | FastAPI type in `reactive/` |
| Load memoization | `LoadCache` | procedural `cache.py` |
| Dirtied keys | `MutationTracker` | scattered ContextVar helpers |
| Cross-worker fan-out | `InvalidationBackend` + `InvalidationHub` | Redis in `reactive/` |
| Client manifest | `MountedManifest` | loose dict parsing only |
| Loaded asset URLs | `LoadedAssets` | `parse_loaded_assets()` |
| OOB swap walk | functions in `oob.py` | `OobSwaps` class (algorithm, not entity) |
| Dev guardrails | module functions + `_DevConfig` | public class |

## Classification rules

- **Entity / aggregate** — identity, lifecycle (`ReactiveComponent`, `LoadCache`)
- **Value object** — parse result, no mutable identity (`MountedManifest.parse` output)
- **Service / hub** — coordinates subsystem (`InvalidationHub`, `MutationTracker`)
- **Algorithm** — stateless transform over inputs (`oob_swaps`, `interpolate_reactive_keys`)
- **Port / ABC** — extension point (`ClientBackend`, `InvalidationBackend`)

## Flag

- **P2:** Procedural module name for a single dominant class (`cache` vs `LoadCache`)
- **P2:** Framework name on generic adapter (`FastAPI*` when only `.headers` is used)
- **P3:** Internal dataclass (`_Candidate`) exposed or imported outside module
- **P3:** Class that should be a function (no state, no extension point)

## Process

1. List public classes and primary functions in scope.
2. Map each to a domain concept from the table (or document gap).
3. Check filenames match dominant type (`load_cache.py` ✓, `mutations.py` + `MutationTracker` ✓).

## Report

Use CONVENTIONS template.
