---
name: module-placement-audit
description: >-
  Audit Python package layering—which modules belong in core, reactive, integrations,
  or utils; framework-specific code in generic layers; forbidden upward imports.
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
integrations/  →  reactive/  →  core/  →  utils.py
```

| Layer | Holds | Must not hold |
|-------|-------|---------------|
| `pyjinhx/integrations/` | FastAPI middleware, Redis backend, Starlette request adapters | Core render algorithms |
| `pyjinhx/reactive/` | ABCs, hubs, reactive algorithms, payload parsing | FastAPI/Redis concrete types |
| `pyjinhx/core/` | Renderer, finder, registry, parser | Framework middleware |
| `pyjinhx/utils.py` | HTML splice, path helpers, client runtime read | Reactive key coercion |

## Precedents (cite in findings)

- `FastAPIClientBackend` → `integrations/fastapi.py` (not `reactive/backend.py`)
- `RedisInvalidationBackend` → `integrations/redis.py` (not `reactive/invalidation.py`)
- `InvalidationHub` + `InvalidationBackend` ABC stay in `reactive/invalidation.py`
- `ClientBackend` ABC stays in `reactive/backend.py`

## Checklist

- [ ] No `from pyjinhx.integrations` inside `reactive/` or `core/`
- [ ] Framework names (`FastAPI`, `Starlette`, `Redis`) only in `integrations/` or config wiring
- [ ] Config (`config/__init__.py`) wires hubs at startup; does not embed integration logic
- [ ] Domain reactive code not re-exported through `utils.py`

## Import scan

```bash
rg 'from pyjinhx\.integrations' pyjinhx/reactive pyjinhx/core
rg 'from pyjinhx\.reactive' pyjinhx/integrations
rg 'fastapi|starlette|redis|fakeredis' pyjinhx/reactive pyjinhx/core --glob '*.py' -i
```

## Report

Use CONVENTIONS template. Severity: **P1** for upward/wrong-layer imports; **P2** for concrete adapter in generic module.
