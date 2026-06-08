---
name: indirection-audit
description: >-
  Audit Python code for unnecessary indirection—thin wrappers, one-line factories,
  module functions that only delegate to classmethods, nested closures for capture,
  and internal re-export shims. Use when the user mentions indirection, wrappers,
  aliases, "just calls", or wants a delegation cleanup pass. Read-only report.
disable-model-invocation: true
---

# Indirection audit

## Audit ownership

**I own:** finding symbols that exist only to hop to another symbol (internal to the package).

**I don't own:** intentional package-boundary re-exports in `pyjinhx/__init__.py`, behavioral duplication (→ `duplication-audit`), export policy (→ `public-api-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## What counts as indirection (flag)

| Pattern | pyjinhx precedent | Fix shape |
|---------|-------------------|-----------|
| Module fn → classmethod only | removed `invalidate()` → `LoadCache.invalidate` | Delete wrapper; call classmethod |
| One-line factory | removed `FastAPIClientBackend.from_request` | Use constructor |
| Parse wrapper | removed `parse_loaded_assets` | Export `LoadedAssets.parse` |
| Nested closure for capture | old `_cached_load` in `install_cached_load` | Store on class (`_pjx_raw_load`); one shared classmethod |
| Migration shim module | deleted `client.py` re-export | Migrate imports; delete shim |
| Classmethod → module fn only | N/A if module fn **is** the implementation | OK |

## What is OK (do not flag)

- `pyjinhx/__init__.py` re-exporting `FastAPIClientBackend` from `integrations.fastapi`
- Module-level `enable_reactive_dev()` with module-private `_DevConfig` (implementation lives there)
- Lazy imports inside functions to break cycles

## Mechanical search

```bash
# Single-return delegation (review hits manually)
rg -n 'def \w+\([^)]*\):\n    return ' pyjinhx/ -U --multiline-dotall

rg 'return \w+\.\w+\(' pyjinhx/ --glob '*.py'
rg 'from pyjinhx\.reactive\.(\w+) import' pyjinhx/reactive/ --glob '*.py'
```

Review each hit: delegation vs real logic.

## Checklist

- [ ] No `def foo(...): return Bar.foo(...)` in same package (except `__init__.py`)
- [ ] No `@classmethod` that only forwards to a module function
- [ ] No per-class nested functions when state can live on the class (`_pjx_*`)
- [ ] No duplicate public names (function + classmethod) for same behavior
- [ ] Temporary migration modules removed after call-site updates

## Report

Use CONVENTIONS template. Typical severity: **P2** (internal), **P1** if public API exposes both wrapper and canonical symbol.
