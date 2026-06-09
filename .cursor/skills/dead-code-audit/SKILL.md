---
name: dead-code-audit
description: >-
  Audit pyjinhx for dead code—removed API ghosts in code/docs/tests, symbols with
  no callers, obsolete backward-compat paths, unused parameters, and tests for
  deleted behavior. Use after refactors, API removals, or when the user asks to
  "sweep for dead code", "find unused code", or "remove leftovers". Read-only report.
disable-model-invocation: true
---

# Dead code audit

## Audit ownership

**I own:** symbols and paths with no live callers, removed-API remnants, obsolete compat shims, tests/docs for deleted behavior.

**I don't own:** thin wrappers that still have callers (→ `indirection-audit`), export policy (→ `public-api-audit`), intentional asymmetry (→ `duplication-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Scope

Default: `pyjinhx/`, `tests/`, `examples/`, `docs/`, `.cursor/skills/`.

User may narrow (e.g. `pyjinhx/reactive/` only). Include docs when user says "full sweep".

## Categories

| Category | Hunt for | Typical severity |
|----------|----------|------------------|
| **Removed API ghost** | Symbol deleted from package but still referenced | P1 in docs/examples; P2 in code/tests |
| **Zero-caller definition** | Function/class/method defined, never imported or called | P2 |
| **Obsolete compat path** | Branch only serving old wire format or migration | P2 |
| **Unused parameter** | Public/internal param never passed by any caller | P3 |
| **Dead infrastructure** | Fields/indexes for removed feature (e.g. stem buckets) | P2 |
| **Orphan test** | Test asserts removed behavior or imports removed symbol | P2 |
| **Stale skill/doc grep** | Audit skills hunting symbols that no longer exist | P3 |

## Known removed symbols (pyjinhx)

Re-grep after each breaking reactive/API change. Absence in `pyjinhx/` but presence elsewhere = ghost.

```
mutation_scope
coerce_dirty_args
interpolate_reactive_keys
MutationKey.instance_key
MutationKey.dirty_keys
dirty_keys
resolve_mounted
resolve_effective_dirtied
warn_reactive_render_without_mounted
get_load_context
load_scope
fastapi_client_backend
parse_loaded_assets
client_has_mounted_manifest
data-pjx-key
```

Also hunt stale **usage patterns** (not necessarily symbol names):

```
render(.*dirtied=
render(.*mounted=
manifest.*"key"
```

## Intentional (do not flag without evidence)

| Item | Why it stays |
|------|----------------|
| `_render(client=...)` | Tests pass explicit client for asset/runtime paths |
| `ClientBackend.resolve_client(explicit)` | Supports `_render(client=request)` |
| `_pjx_key` | Internal load-cache identity |
| `depends_on()` default | Load-cache reverse index + dev validation |
| `MutationTracker.render_was_consumed()` | Dev guardrail |
| `pyjinhx/__init__.py` re-exports | Public API surface |

Compat shims: flag only when **zero callers** remain (grep the shim body, not just the name).

## Process

1. **Confirm scope** and whether docs/skills/examples are in scope.
2. **Ghost scan** — run mechanical greps (below) for removed symbols and stale patterns.
3. **Definition scan** — for symbols touched by recent refactors, count references:

```bash
# Replace SYMBOL; expect hits in definition file only (+ maybe tests to delete)
rg -l '\bSYMBOL\b' pyjinhx tests examples docs .cursor/skills
```

4. **Export vs usage** — compare `pyjinhx.__all__` to `tests/36_public_api_test.py` and doc tables; flag exports with no docs/tests if newly added.
5. **Branch scan** — read compat helpers (`_manifest_load_arg`, `resolve_client`, etc.): is every branch reachable?
6. **Test scan** — tests whose names/descriptions reference removed APIs (`mutation_scope`, `data-pjx-key`, instance-tier dirty keys).
7. **Classify** each hit: delete | migrate caller | document as intentional compat | false positive.
8. **Do not delete** unless user asks for remediation.

## Mechanical checks

```bash
# Removed API ghosts (expand list as APIs drop)
rg -n 'mutation_scope|coerce_dirty_args|interpolate_reactive_keys|dirty_keys|resolve_mounted|resolve_effective_dirtied|warn_reactive_render_without_mounted|get_load_context|fastapi_client_backend|data-pjx-key' \
  pyjinhx tests examples docs .cursor/skills

# Stale render kwargs in docs/examples (not in pyjinhx — may be intentional in migration docs)
rg -n 'render\([^)]*dirtied=|render\([^)]*mounted=' docs examples .cursor/skills

# Top-level invalidate wrapper (canonical: LoadCache.invalidate)
rg -n 'from pyjinhx import .*invalidate|pyjinhx\.invalidate\b' docs examples README.md

# Unused imports (run ruff; triage F401 in scope only)
uv run ruff check pyjinhx/ --select F401
```

After remediation candidates are identified, verify survivors:

```bash
uv run pytest tests/ -q
uv run ruff check .
```

## Checklist

- [ ] No removed symbols in `pyjinhx/` (except CHANGELOG/historical notes if any)
- [ ] No removed symbols in `tests/` imports or assertions
- [ ] `docs/` and `examples/` use current API (`PjxKey`, `Cls.render(*args)`, `@mutates` state keys only)
- [ ] No orphan compat branches (manifest `key` alias, stem invalidation index, etc.) without tests or callers
- [ ] No tests asserting deleted behavior unless explicitly marked legacy
- [ ] Audit skills grep current symbols (`warn_reactive_render_without_client`, not `..._mounted`)
- [ ] `__all__` / `36_public_api_test.py` / `docs/reference/public-api.md` agree

## Relationship to sibling audits

| Lens | Overlap |
|------|---------|
| `public-api-audit` | Doc/export drift; dead-code adds **code-path** and **zero-caller** analysis |
| `indirection-audit` | Wrapper with callers ≠ dead; wrapper with **zero** callers → dead-code P2 |
| `duplication-audit` | Parallel paths where one side is never invoked → dead-code |

Run **after** `public-api-audit` in a full sweep (docs table first, then orphan code).

## Report

Use CONVENTIONS template.

Severity guide:

- **P1** — Removed API still exported, documented as current, or called from production `pyjinhx/` code
- **P2** — Dead function/branch/test, obsolete infra, ghost in examples/tests
- **P3** — Unused parameter, stale skill grep line, comment referencing removed API

**Fix shape** examples:

- Delete symbol and migrate last caller
- Remove compat branch + test that only exercised compat
- Update doc/snippet to canonical API
- Drop unused parameter from signature (if all callers updated)
