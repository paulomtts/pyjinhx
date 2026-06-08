---
name: duplication-audit
description: >-
  Audit for duplicated workflows and parallel call sequences that will drift—same
  orchestration in two modules, duplicate parsing/validation, identical decorator
  and context-manager bodies. Use when reviewing refactors, merge conflicts, or
  "keep these in sync" code. Read-only report; documents intentional asymmetry.
disable-model-invocation: true
---

# Duplication audit

## Audit ownership

**I own:** parallel workflows, copy-pasted orchestration, mergeable identical blocks.

**I don't own:** thin wrappers (→ `indirection-audit`), file splits (→ `file-responsibility-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Hunt targets

1. **Parallel orchestration** — same step sequence in 2+ entrypoints.
   - Fixed: `component.py` + `base.py` render → `reactive/render.py` `reactive_render_bundle`.
2. **Duplicate parsing/validation** — two ways to answer the same question.
   - Fixed: `client_has_mounted_manifest` vs manifest parse → `MountedManifest.is_present`.
3. **Decorator + context manager** — identical bodies.
   - Fixed: `@mutates` and `mutation_scope` → `MutationTracker.record`.

## Intentional asymmetry (document, don't merge blindly)

| Path | Difference | Example |
|------|------------|---------|
| Class render | Pre-invalidate before primary | `invalidate_before_primary=True` |
| Instance render | Invalidate inside `oob_swaps` | `invalidate_before_primary=False` |

Flag as **documented divergence** if asymmetry is required; **merge candidate** if behavior should match.

## Process

1. List entrypoints for the scope (public methods, route handlers, `render()` paths).
2. For each pair sharing nouns (`render`, `invalidate`, `parse`, `load`), diff call sequences.
3. Grep repeated 5+ line blocks:

```bash
rg -n 'warn_reactive_render_without_mounted|resolve_effective_dirtied|mark_reactive_render_consumed' pyjinhx/
```

4. Classify: merge candidate | documented divergence | unrelated.

## Checklist

- [ ] No duplicated render/mutation orchestration across `core/` and `reactive/`
- [ ] Parsing logic has one canonical implementation per wire format
- [ ] Shared mutation recording is one code path
- [ ] Intentional behavioral differences are named in code or docs

## Report

Use CONVENTIONS template. Severity: **P1** for orchestration drift risk; **P3** for minor repeated literals.
