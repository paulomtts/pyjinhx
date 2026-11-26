# Code audit conventions (pyjinhx)

Shared by all code-audit skills under `.claude/skills/`. Each skill links here instead of duplicating rules.

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
3. **Stateful subsystems → explicit request scope, not module globals** — `LoadCache` (`pyjinhx/reactive/cache.py`) is request-scoped through `request_scope()` in `pyjinhx/rendering/session.py`; dirty-key tracking runs through `add_dirtied()` / `get_dirtied()` in `pyjinhx/rendering/session.py`; `PjxContext` (`pyjinhx/context.py`) is the read-only ContextVar-backed handle onto that state.
4. **Pure transforms stay functions** — e.g. key coercion in `pyjinhx/reactive/keys.py` (`coerce_reactive_key`, `coerce_reactive_keys`). No class wrapper around a stateless transform.
5. **Ergonomic decorators stay module-level** — `@mutates` in `pyjinhx/reactive/mutations.py` is a module-level decorator that records keys via the module-level `dirty()`; it is not a method on a tracker object.
6. **Package `__init__.py` re-exports OK; internal wrappers not OK** — a package `__init__` may re-export its public surface and document the package (see `pyjinhx/builtins/__init__.py`), but must not add a second implementation layer over its submodules.
7. **Packages are named for a role; modules for their job** — `pyjinhx/document/` (static reading of a pjx document, imports nothing else in pyjinhx), `pyjinhx/components/` (what a component class is and how one comes to exist: `base`, `classless`, `discovery`, `importer`, `props_header`), `pyjinhx/rendering/` (one request's render: `pipeline`, `session`, `template_context`, `segments`, `root_attrs`, `assets`, `render_cache`, `registry`), plus `reactive/`, `integrations/`, `client/` and `builtins/`. The top level is the wiring layer and command line only: `config.py`, `context.py`, `app_context.py`, `dev.py`, `manifest.py`, `stubgen.py`. New helpers go in the module that owns the concern, or in a new named module — never into a catch-all `utils`/`helpers` dumping ground. `__init__.py` of `document/`, `components/` and `rendering/` stay empty so `import pyjinhx` stays free of pydantic and jinja2.

## Layer map

```
integrations/ , client/ , builtins/
        │
        ▼
    reactive/
        │
        ▼
rendering/  ──▶  components/  ──▶  document/
```

- `integrations/` may import from `reactive/`, `rendering/`, `components/` and the top-level wiring modules (`config.py`, …).
- `client/` and `builtins/` may import from `reactive/`, `rendering/` and `components/`; nothing below them imports back up.
- `reactive/` must not import from `integrations/`, `client/` or `builtins/`.
- `rendering/` and `components/` may import from `reactive/` only where render paths require it (`rendering/render_cache.py`); avoid pulling `integrations/` upward into them. `document/` imports nothing else in pyjinhx.
- The exact edges are the table in `tests/packaging/test_import_graph.py`.

## Suite order

When running a full sweep, run the audits in this order:

1. domain-entity-audit
2. duplication-audit
3. indirection-audit
4. public-api-audit
5. dead-code-audit

Merge duplicate findings at the same location; keep the highest severity.
