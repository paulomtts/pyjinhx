---
name: public-api-audit
description: >-
  Audit pyjinhx public API surface—pyjinhx.__all__, top-level exports vs canonical
  implementations, docs/reference/public-api.md alignment, tests/36_public_api_test.py.
  Use before releases, after refactors, or when removing deprecated symbols. Read-only.
disable-model-invocation: true
---

# Public API audit

## Audit ownership

**I own:** `pyjinhx/__init__.py` `__all__`, docs index vs exports, public-api test alignment.

**I don't own:** internal wrapper removal (→ `indirection-audit`), where impl files live (→ `module-placement-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Rules

1. Every `__all__` name points at **one canonical implementation** (no alias assignment in `__init__.py`).
2. Removed symbols must be absent from:
   - `docs/reference/public-api.md`
   - `docs/api/*.md`
   - `README.md` examples (or updated to canonical names)
3. Integration concretes may be re-exported from top-level if impl lives in `integrations/`:
   - `from pyjinhx.integrations.fastapi import FastAPIClientBackend` in `__init__.py` ✓
4. Prefer classmethods on exported types over free function wrappers:
   - `LoadCache.invalidate`, `MountedManifest.parse`, `MutationTracker.record`
5. README documents API shape decisions when exports change.

## Checklist

- [ ] `import pyjinhx; set(pyjinhx.__all__) == set(dir intended)`
- [ ] No removed symbols in docs (`get_load_context`, `fastapi_client_backend`, `invalidate`, etc.)
- [ ] `tests/36_public_api_test.py` imports match `__all__`
- [ ] Examples use canonical names (`LoadContext.current`, not `get_load_context`)
- [ ] Breaking renames noted in README if user-facing

## Mechanical checks

```bash
python -c "import pyjinhx; print(sorted(pyjinhx.__all__))"
rg 'get_load_context|load_scope|fastapi_client_backend|parse_loaded_assets|client_has_mounted_manifest|set_invalidation_backend|get_load_cache_scope' docs/ README.md
```

Compare `docs/reference/public-api.md` table to `pyjinhx.__all__`.

## Report

Use CONVENTIONS template. Severity: **P1** for docs exporting removed APIs; **P2** for `__all__`/test drift; **P3** for example snippets.
