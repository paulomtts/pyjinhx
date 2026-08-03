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
| Per-request mutable state | Store on the request-scoped session; expose module functions | `pyjinhx/session.py` stores + `cache_get`/`cache_put`/`invalidate` (`reactive/cache.py`) |
| Dirtied-key accumulation | Module functions over session state | `dirty()` (`reactive/mutations.py:65`) → `add_dirtied()`/`get_dirtied()` (`session.py:166,158`) |
| Request-scoped opaque DI bag | Frozen dataclass + classmethod accessor | `PjxContext` / `PjxContext.current` (`context.py:30,48`) |
| Pure input → output | Module functions | `coerce_reactive_key` (`reactive/keys.py:14`), `oob_swaps`/`walk_manifest` (`reactive/fanout.py:450,307`) |
| Decorator ergonomics | Decorator and its imperative twin share one sink | `mutates()` (`reactive/mutations.py:31`) and `dirty()` both call `add_dirtied()` |
| Plugin extension point | `Protocol`, no state | `IntegrationBackend` (`integrations/base.py:35`), registered via `register_backend()` |
| Instance lookup | Module functions over session state | `register_instance` / `resolve` (`pyjinhx/registry.py`) — there is no `Registry` class |
| Dev toggles | Module fns + private dataclass | `enable_reactive_dev` / `_DevConfig` (`dev.py:34,24`) |

## Hunt patterns

```bash
rg -n '^_\w+: (ContextVar|threading\.Lock)' pyjinhx/ --glob '*.py'
rg -n '^_[a-z_]+ = ' pyjinhx/reactive --glob '*.py'
rg -n 'get_cache_store|get_cache_forward|get_cache_reverse|current_session' pyjinhx/
```

For each module-global cluster, ask: should this be methods on one class?

## Anti-patterns (flag)

- **P2:** Process-global mutable state that should be request-scoped (must live on the session, not a module dict)
- **P2:** A wrapper class introduced purely to hold functions that already read session state
- **P3:** Class with a single `@staticmethod` and no state (prefer a function unless it groups a parse API, as `MountedManifest.parse` does)

## OK patterns (do not flag)

- `_dev_config` module global with `enable_reactive_dev` / `disable_reactive_dev` as the canonical dev API (`pyjinhx/dev.py`)
- Request state entered via the free `request_scope()` contextmanager (`pyjinhx/session.py:224`) and read via `get_load_context()` (`session.py:213`)
- `PjxContext.current` classmethod over a module-level ContextVar
- Lazy import inside a function to avoid an import cycle
- Grouping related parse helpers as `@staticmethod`s on a wire-format type (`LoadedAssets`, `MountedManifest`, `TriggerManifest`)

## Checklist

- [ ] Request-scoped state lives on the session, not in module globals
- [ ] Extension points are `Protocol`s with no state (`IntegrationBackend`)
- [ ] Pure key transforms remain functions in `pyjinhx/reactive/keys.py`
- [ ] Tests reset state by re-entering `request_scope()`, not by poking module globals

## Report

Use CONVENTIONS template.
