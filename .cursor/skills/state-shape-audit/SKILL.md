---
name: state-shape-audit
description: >-
  Audit where mutable state lives in Python modules—module globals and ContextVars
  vs class classmethods, pure functions vs hubs, ABC vs coordinator split. Use when
  reviewing singletons, request scope, caches, or "should this be a class". Read-only.
disable-model-invocation: true
---

# State shape audit

## Audit ownership

**I own:** module-level mutable state, function vs classmethod choice for stateful subsystems.

**I don't own:** file splits, domain naming, thin wrappers.

Read: [CONVENTIONS.md](../code-audit-sweep/CONVENTIONS.md).

## Shape rules

| Situation | Shape | pyjinhx example |
|-----------|-------|-----------------|
| ContextVar + locks + process/request state | Class with `@classmethod` | `LoadCache`, `MutationTracker`, `InvalidationHub`, `ClientBackend` |
| Request-scoped opaque DI bag | Static methods on frozen dataclass base | `LoadContext` |
| Pure input → output | Module functions | `coerce_reactive_key`, `pjx_load_field_names`, `PjxLoad` validation |
| Decorator ergonomics | Module decorator → class method | `@mutates` → `MutationTracker.record` |
| Plugin extension point | ABC, no hub state | `InvalidationBackend` |
| Runtime coordinator | Hub class | `InvalidationHub` |
| Dev toggles | Module fn + private dataclass | `enable_reactive_dev`, `_DevConfig` |

## Hunt patterns

```bash
rg '^_\w+: (ContextVar|threading\.Lock)' pyjinhx/ --glob '*.py'
rg '^_[a-z_]+ = ' pyjinhx/reactive --glob '*.py'
```

For each module-global cluster, ask: should this be methods on one class?

## Anti-patterns (flag)

- **P2:** Multiple free functions mutating the same module-global ContextVar (pre-`LoadCache` style)
- **P2:** Instance singleton injection for request scope (reverted pattern—use classmethod + ContextVar)
- **P3:** Class with a single `@staticmethod` and no state (prefer function unless grouping API)

## OK patterns (do not flag)

- `_dev_config` module global with functions as canonical dev API
- Module-level ContextVar with static methods on owning type (`LoadContext.current` / `Registry.request_scope` pattern)
- Lazy import inside method to avoid cycles
- `CacheScope` enum at module level next to `LoadCache` class

## Checklist

- [ ] Each ContextVar has one owning class
- [ ] Hubs separate from ABCs (`InvalidationHub` vs `InvalidationBackend`)
- [ ] Pure key/string transforms remain functions in `keys.py`
- [ ] Tests reset via `.clear()`, `.reset()`, `.reset_request()` on owning class

## Report

Use CONVENTIONS template.
