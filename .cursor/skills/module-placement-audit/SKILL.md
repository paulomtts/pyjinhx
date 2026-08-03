---
name: module-placement-audit
description: >-
  Audit Python package layering—which modules belong in the flat top-level modules,
  `reactive/`, `client/`, or `integrations/`; framework-specific code in generic layers; forbidden upward imports.
  Use when asking "should this live in this file", moving adapters, or reviewing
  integration boundaries. Read-only report.
disable-model-invocation: true
---

# Module placement audit

## Audit ownership

**I own:** layer violations, framework code in generic packages, import direction.

**I don't own:** file size splits (→ `file-responsibility-audit`), entity naming (→ `domain-entity-audit`).

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Layer rules

```
integrations/  →  reactive/  →  flat top-level pyjinhx/*.py
                      client/  ↗
```

| Layer | Holds | Must not hold |
|-------|-------|---------------|
| `pyjinhx/integrations/` | `IntegrationBackend` Protocol (`base.py`), `FastAPIBackend` (`fastapi.py`), backend registration | render or fan-out algorithms |
| `pyjinhx/reactive/` | `ReactiveComponent`, `PjxKey`, cache/mutation/fan-out functions, `ReactiveResponse` | concrete web-framework types |
| `pyjinhx/client/` | runtime injection and wire-format parsing (`inject.py`, `pjx.js`, htmx bundle) | reactive invalidation policy |
| flat `pyjinhx/*.py` | kernel: `component.py`, `rendering.py`, `session.py`, `registry.py`, `context.py`, `assets.py`, `config.py`, `dev.py`, … | anything importing `reactive/` or `integrations/` |

## Precedents (cite in findings)

- `FastAPIBackend` → `pyjinhx/integrations/fastapi.py` (not `reactive/`)
- `IntegrationBackend` Protocol stays in `pyjinhx/integrations/base.py`; `register_backend()` / `get_backend()` live beside it
- Fan-out and OOB swap emission stay in `pyjinhx/reactive/fanout.py`
- Request-scoped stores stay in `pyjinhx/session.py`; `reactive/cache.py` reads them, it does not own them
- Wire-format parsing (`LoadedAssets`, `MountedManifest`, `TriggerManifest`) stays in `pyjinhx/client/inject.py`
- The renderer module is `pyjinhx/rendering.py` — the pre-rewrite name is stale and must not appear

## Checklist

- [ ] No `from pyjinhx.integrations` inside `reactive/`, `client/`, or the flat top-level modules
- [ ] No `from pyjinhx.reactive` inside the flat top-level modules (`reactive/` sits above the kernel)
- [ ] Framework names (`fastapi`, `starlette`) only under `pyjinhx/integrations/`
- [ ] `config.py` wires backends at startup; it does not embed integration logic

## Import scan

```bash
rg 'from pyjinhx\.integrations' pyjinhx/reactive pyjinhx/client
rg 'from pyjinhx\.reactive' pyjinhx/integrations
rg 'from pyjinhx\.(reactive|integrations|client)' pyjinhx/*.py
rg 'fastapi|starlette' pyjinhx/reactive pyjinhx/client --glob '*.py' -i
```

The only currently-expected hit from these scans is `pyjinhx/integrations/fastapi.py:28: from pyjinhx.reactive.response import ReactiveResponse`, which follows the allowed direction.

## Report

Use CONVENTIONS template. Severity: **P1** for upward/wrong-layer imports; **P2** for concrete adapter in generic module.
