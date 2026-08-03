---
name: public-api-audit
description: >-
  Audit pyjinhx public API surface—pyjinhx.__all__, top-level exports vs canonical
  implementations, docs/reference/public-api.md alignment, tests/test_package_layout.py.
  Use before releases, after refactors, or when removing deprecated symbols. Read-only.
disable-model-invocation: true
---

# Public API audit

## Audit ownership

**I own:** `pyjinhx/__init__.py` `__all__`, docs index vs exports, public-api test alignment.

**I don't own:** internal wrapper removal (→ `indirection-audit`), where impl files live (→ `module-placement-audit`), zero-caller symbols (→ `dead-code-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Rules

1. Every `__all__` name points at **one canonical implementation** (no alias assignment in `__init__.py`).
2. Removed symbols must be absent from:
   - `docs/reference/public-api.md`
   - `docs/api/*.md`
   - `README.md` examples (or updated to canonical names)
3. Integration concretes may be re-exported from top-level if impl lives in `integrations/`:
   - `from pyjinhx.integrations.fastapi import FastAPIBackend` in `__init__.py` ✓
4. Prefer classmethods on exported types over free function wrappers:
   - `MountedManifest.parse`, `TriggerManifest.parse` (and keep `reactive.cache.invalidate` a module fn — it has no owning class)
5. README documents API shape decisions when exports change.

## Checklist

- [ ] `import pyjinhx; set(pyjinhx.__all__) == set(dir intended)`
- [ ] No removed symbols in docs (`mutation_scope`, `dirty_keys`, `StateKey`, `PyJinhxSettings`, `LoadContext`, `PjxLoad`, etc.)
- [ ] New exports documented (`PjxKey`, `TriggerManifest`, `PJX_TRIGGER_HEADER`)
- [ ] `tests/test_package_layout.py` `EXPECTED_EXPORTS` matches `pyjinhx.__all__`
- [ ] Examples use canonical names (`PjxContext`, not `LoadContext`; `PjxKey`, not `PjxLoad`)
- [ ] Breaking renames noted in README if user-facing

## Mechanical checks

```bash
python -c "import pyjinhx; print(sorted(pyjinhx.__all__))"
rg 'mutation_scope|dirty_keys|load_scope|data-pjx-key|dirtied=|mounted=|client_has_mounted_manifest|StateKey|PyJinhxSettings|LoadContext|PjxLoad' docs/ README.md
```

Compare `docs/reference/public-api.md` table to `pyjinhx.__all__`.

## Report

Use CONVENTIONS template. Severity: **P1** for docs exporting removed APIs; **P2** for `__all__`/test drift; **P3** for example snippets.
