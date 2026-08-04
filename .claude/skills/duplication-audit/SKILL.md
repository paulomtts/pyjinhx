---
name: duplication-audit
description: >-
  Audit for duplicated workflows and parallel call sequences that will drift—same
  orchestration in two modules, duplicate parsing/validation, identical decorator
  and context-manager bodies. Use when reviewing refactors, merge conflicts, or
  "keep these in sync" code. Read-only report; documents intentional asymmetry.
---

# Duplication audit

## Audit ownership

**I own:** parallel workflows, copy-pasted orchestration, mergeable identical blocks.

**I don't own:** thin wrappers (→ `indirection-audit`).

Read: [CONVENTIONS.md](../_shared/CONVENTIONS.md).

## Hunt targets

1. **Parallel orchestration** — same step sequence in 2+ entrypoints.
   - Canonical: one render path through `pyjinhx/rendering.py`; the reactive route composes its result into `ReactiveResponse` (`pyjinhx/reactive/response.py:14`).
2. **Duplicate parsing/validation** — two ways to answer the same question.
   - Canonical: each wire header is parsed exactly once, by its own type's `parse()` in `pyjinhx/client/inject.py` (`LoadedAssets`, `MountedManifest`, `TriggerManifest`).
3. **Mutation recording** — must stay one code path.
   - Canonical: `mutates()` and `dirty()` (`pyjinhx/reactive/mutations.py:31,65`) both funnel into `add_dirtied()` (`pyjinhx/session.py:166`). Any third route that writes dirtied keys is a merge candidate.
4. **Key coercion** — `coerce_reactive_key` / `coerce_reactive_keys` (`pyjinhx/reactive/keys.py:14,33`) are the only normalizers; inline `str()`-ing of keys is duplication.

## Intentional asymmetry (document, don't merge blindly)

No invalidation-ordering asymmetry exists in this codebase: there is a single render path, and `invalidate()` (`pyjinhx/reactive/cache.py:105`) is called once per request against the dirtied set. Do not cite an `invalidate_before_primary` flag — it does not exist.

Record real asymmetries here only when both branches are grep-confirmed. Flag as **documented divergence** when the difference is required and named in code or docs; **merge candidate** when the behavior should match.

## Process

1. List entrypoints for the scope (public methods, route handlers, `render()` paths).
2. For each pair sharing nouns (`render`, `invalidate`, `parse`, `load`), diff call sequences.
3. Grep repeated 5+ line blocks:

```bash
rg -n 'add_dirtied|coerce_reactive_keys|cache_put|walk_manifest|oob_swaps' pyjinhx/
```

4. Classify: merge candidate | documented divergence | unrelated.

## Checklist

- [ ] No duplicated render/mutation orchestration between the flat kernel modules and `reactive/`
- [ ] Parsing logic has one canonical implementation per wire format
- [ ] Shared mutation recording is one code path
- [ ] Intentional behavioral differences are named in code or docs

## Report

Use CONVENTIONS template. Severity: **P1** for orchestration drift risk; **P3** for minor repeated literals.
