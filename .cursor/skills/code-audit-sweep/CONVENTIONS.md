# Code audit conventions (pyjinhx)

Shared by all skills in the code-audit suite. Child skills link here instead of duplicating rules.

## Mode

**Read-only by default.** Produce a report and punch list. Fix findings only when the user explicitly asks for remediation in a follow-up pass.

After fixes: `uv run ruff check .` and `uv run pytest`.

## Report template

```markdown
# [Audit name] — [scope path]

## Summary
[1–2 sentences: count by severity]

## Findings

### [P1|P2|P3] Title
- **Location:** path:line
- **Lens:** skill name
- **Issue:** what violates the rule
- **Precedent:** pyjinhx example (if any)
- **Fix shape:** one concrete direction (not full implementation)

## Punch list
- [ ] ...
```

## Severity rubric

| Level | Meaning |
|-------|---------|
| P1 | Wrong layer, duplicate orchestration that will drift, misleading public API, removed API still live in code/docs |
| P2 | Indirection, misplaced integration code, module globals for mutable state, dead symbols/branches/tests |
| P3 | Naming, minor duplication, doc drift, unused parameters |

## pyjinhx design rules

Cite these in findings when relevant:

1. **One implementation layer** — no internal module function that only delegates to a classmethod (or the reverse).
2. **Protocol in `integrations/base.py`; impl per framework** — `IntegrationBackend` (`is_installed`, `mark_installed`, `mount_static`, `on_startup`, `on_shutdown`, `to_response`) is defined in `pyjinhx/integrations/base.py` and wired through `register_backend()` / `get_backend()`; concrete adapters live one-per-framework, e.g. `FastAPIBackend` in `pyjinhx/integrations/fastapi.py`.
3. **Stateful subsystems → explicit request scope, not module globals** — `LoadCache` (`pyjinhx/reactive/cache.py`) is request-scoped through `request_scope()` in `pyjinhx/session.py`; dirty-key tracking runs through `add_dirtied()` / `get_dirtied()` in `pyjinhx/session.py`; `PjxContext` (`pyjinhx/context.py`) is the read-only ContextVar-backed handle onto that state.
4. **Pure transforms stay functions** — e.g. key coercion in `pyjinhx/reactive/keys.py` (`coerce_reactive_key`, `coerce_reactive_keys`). No class wrapper around a stateless transform.
5. **Ergonomic decorators stay module-level** — `@mutates` in `pyjinhx/reactive/mutations.py` is a module-level decorator that records keys via the module-level `dirty()`; it is not a method on a tracker object.
6. **Package `__init__.py` re-exports OK; internal wrappers not OK** — a package `__init__` may re-export its public surface and document the package (see `pyjinhx/builtins/__init__.py`), but must not add a second implementation layer over its submodules.
7. **Top level stays flat and named for its job** — `pyjinhx/` holds one module per concern (`component.py`, `rendering.py`, `session.py`, `registry.py`, `assets.py`, `config.py`, `context.py`, `descriptor.py`, `discovery.py`, `root_attrs.py`, `render_context.py`, `markers.py`, `segments.py`, `props_header.py`, `classless.py`, `dev.py`, `app_context.py`) plus the `reactive/`, `integrations/`, `client/` and `builtins/` subpackages. New helpers go in the module that owns the concern, or in a new named module — never into a catch-all `utils`/`helpers` dumping ground.

## Layer map

```
integrations/ , client/ , builtins/
        │
        ▼
    reactive/
        │
        ▼
top-level modules (component.py, rendering.py, session.py, registry.py, …)
```

- `integrations/` may import from `reactive/` and the top-level modules (`config.py`, `session.py`, `rendering.py`, …).
- `client/` and `builtins/` may import from `reactive/` and the top-level modules; nothing below them imports back up.
- `reactive/` must not import from `integrations/`, `client/` or `builtins/`.
- Top-level modules (e.g. `rendering.py`) may import from `reactive/` where render paths require it; avoid pulling `integrations/` upward into them.

## Suite order (orchestrator)

When running a full sweep, child audits run in this order:

1. file-responsibility-audit
2. module-placement-audit
3. domain-entity-audit
4. state-shape-audit
5. duplication-audit
6. indirection-audit
7. public-api-audit
8. dead-code-audit

Merge duplicate findings at the same location; keep the highest severity.
