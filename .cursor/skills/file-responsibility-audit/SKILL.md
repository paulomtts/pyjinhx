---
name: file-responsibility-audit
description: >-
  Audit Python files for single responsibility—oversized modules, mixed concerns
  (parsing + algorithm + runtime in one file), misleading filenames, empty package
  __init__ without module maps. Use when a file feels crowded or before splitting
  a module. Read-only report.
disable-model-invocation: true
---

# File responsibility audit

## Audit ownership

**I own:** one-file-one-reason-to-change, LOC thresholds, split recommendations.

**I don't own:** layer placement (→ `module-placement-audit`), entity names (→ `domain-entity-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Thresholds

| Signal | Action |
|--------|--------|
| >250 LOC | Review for split |
| 150–250 LOC | Review if multiple unrelated concerns |
| 240–260 LOC, single cohesive class | Soft ceiling only; defer split (see VALIDATION.md) |
| <80 LOC | Do not split unless concerns are clearly separable |

## Red flags

- Unrelated section nouns in one file (old `client.py`: parsing + `client_script` + `oob_swaps`)
- Filename mismatches primary type (`cache.py` → `load_cache.py` + `LoadCache`)
- Empty `__init__.py` in a subpackage with no module-map docstring
- Private helpers dominating file (>50% LOC) for a different concern than public API

## Split patterns (prefer flat files)

| Concern | Target name |
|---------|-------------|
| Wire format / header parsing | `payload.py` |
| HTMX OOB algorithm | `oob.py` |
| Runtime `<script>` injection | `runtime.py` |
| Shared render orchestration | `rendering.py` |

Do not create nested packages until >12 modules in the directory.

Avoid a target name that collides with a re-exported symbol: `pyjinhx/__init__.py` once did `from pyjinhx.render import render`, which shadowed the `pyjinhx.render` submodule and broke `import pyjinhx.render`; the module is now `rendering.py`.

## When NOT to split

- Tight private helper graph used only by one public function
- Split would introduce circular imports (note as **P3** risk instead)
- File is cohesive but long (e.g. single class with many small methods)

## Process

```bash
wc -l pyjinhx/**/*.py | sort -n
```

For each file over threshold in scope, list public symbols and group by concern.

## pyjinhx reference layout

There is no maintained module map document. Derive the layout from the tree itself:

```bash
ls pyjinhx/ pyjinhx/reactive/ pyjinhx/integrations/ pyjinhx/client/ pyjinhx/builtins/
```

## Report

Use CONVENTIONS template. Severity: **P2** for clear mixed concerns; **P3** for soft LOC overage with cohesion.
