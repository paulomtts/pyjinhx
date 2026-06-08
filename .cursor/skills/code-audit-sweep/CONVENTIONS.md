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
| P1 | Wrong layer, duplicate orchestration that will drift, misleading public API |
| P2 | Indirection, misplaced integration code, module globals for mutable state |
| P3 | Naming, minor duplication, doc drift |

## pyjinhx design rules

Cite these in findings when relevant:

1. **One implementation layer** — no internal module function that only delegates to a classmethod (or the reverse).
2. **ABC + hub in core/reactive; impl in integrations** — e.g. `ClientBackend` in `pyjinhx/reactive/backend.py`, `FastAPIClientBackend` in `pyjinhx/integrations/fastapi.py`; `InvalidationBackend` + `InvalidationHub` vs `RedisInvalidationBackend` in `pyjinhx/integrations/redis.py`.
3. **Stateful subsystems → class + classmethods + ContextVar** — `LoadCache`, `MutationTracker`, `InvalidationHub`, `ClientBackend`, `LoadContext`.
4. **Pure transforms stay functions** — `pyjinhx/reactive/keys.py` coercion/interpolation.
5. **Ergonomic decorators stay module-level** — `@mutates` / `mutation_scope` call `MutationTracker.record`.
6. **Package `__init__.py` re-exports OK; internal wrappers not OK.**
7. **Domain code not in `pyjinhx/utils.py`** — HTML/path/runtime helpers only.

## Layer map

```
integrations/  →  reactive/  →  core/  →  utils.py
```

- `integrations/` may import from `reactive`, `core`, `config`.
- `reactive/` must not import from `integrations/`.
- `core/` may import from `reactive` where render paths require it; avoid pulling integrations upward.

## Suite order (orchestrator)

When running a full sweep, child audits run in this order:

1. file-responsibility-audit
2. module-placement-audit
3. domain-entity-audit
4. state-shape-audit
5. duplication-audit
6. indirection-audit
7. public-api-audit

Merge duplicate findings at the same location; keep the highest severity.
