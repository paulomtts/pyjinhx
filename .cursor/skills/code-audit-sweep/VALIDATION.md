# Dry-run validation (2026-06-07)

Orchestrator dry-run after reactive refactor. Used to calibrate severity and confirm skills are not noisy on clean scope.

## pyjinhx/reactive/

| P1 | P2 | P3 |
|----|----|----|
| 0  | 0  | 0–1 |

**Summary:** Post-refactor reactive package passes all lenses. No layer violations, no thin wrappers, ContextVars owned by hub classes (`LoadCache`, `MutationTracker`, `ClientBackend`) or `LoadContext` static API. Largest file `load_cache.py` (243 LOC) is cohesive single-class; below hard split threshold.

Optional P3 (not reported): `load_cache.py` slightly above 250 LOC soft ceiling — defer split until second concern appears.

## pyjinhx/core/

| P1 | P2 | P3 |
|----|----|----|
| 0  | 1  | 2 |

### P2 — `renderer.py` size (~858 LOC)

- **Status:** Remediated — split into `renderer.py` (~470 LOC orchestration), `render_assets.py`, `tag_expand.py`, `autodiscover.py`.

### P3 — `core/__init__.py` empty

- **Lens:** file-responsibility-audit
- **Issue:** No module-map docstring (reactive `__init__.py` has one).
- **Fix shape:** Add brief docstring map if core grows submodules.

### P3 — `registry.py` module-level `_registry_context`

- **Lens:** state-shape-audit
- **Issue:** ContextVar at module level vs `ClassVar` on `Registry` (matches `LoadContext` pattern).
- **Fix shape:** Optional consolidation onto `Registry` when editing; not inconsistent enough to prioritize.

## Cross-cutting (docs, not code scope)

`public-api-audit` on `docs/` finds stale symbols (`get_load_context`, `fastapi_client_backend`) — **P1 doc drift** when auditing full package + docs. Child skill correctly flags these; reactive code scope alone stays clean.

## Rubric tuning applied

- Cohesive single-class files 240–260 LOC → no finding unless mixed concerns.
- Module-level ContextVar + class static methods (`LoadContext`, `Registry`) → OK, not P2.
- Expected baseline in orchestrator SKILL.md matches reactive dry-run.
