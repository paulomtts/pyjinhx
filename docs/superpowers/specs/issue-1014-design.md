# Issue #1014 — document `state_hash_exclude` guidance for per-render-random fields

Subtask of story #1010, milestone 18 ("Nested reactive OOB ownership"). Narrows Story 2 of `docs/superpowers/specs/2026-08-23-nested-reactive-oob-preserve-design.md` (lines 128-160) to its single deliverable. Docs-only.

## Problem

`ReactiveComponent.state_hash()` (`pyjinhx/reactive/component.py:78-89`) digests `model_dump(mode="json", exclude=set(exclude))` where `exclude` is the class's `state_hash_exclude` (`component.py:60`, default `frozenset({"id"})`). Every declared field that is not excluded therefore feeds the digest. A field whose value is freshly minted on every render — a `uuid4().hex` trace/request id, a `datetime.now()` timestamp not derived from persisted data — makes that instance's hash never repeat.

The consequence is in `pyjinhx/reactive/fanout.py:189-198`: `_hash_gate_drops(fresh_hash, entry)` returns `fresh_hash == entry.get("hash")`, and is the only thing that stops a re-rendered region whose output is byte-identical to what the client already shows from being swapped again. A never-repeating hash means that gate can never fire for that class, so every parent dirty event blasts an `outerHTML` swap over every nested child region regardless of whether the child's own data moved — which is precisely the race window Story 1 (#1009, `hx-preserve` stamping, a disjoint code path) exists to narrow.

The mechanism to avoid this already exists and is already reachable from user code. Nothing is missing but the guidance. **No new hashing mechanism is to be proposed or built.**

## Scope

Documentation edits only, at the two insertion points already identified:

- `docs/reactivity.md:66-68` — the existing `state_hash()` bullet in the reactive-fields list. Extend it (or add adjacent prose/callout) with the per-render-random-field warning.
- `docs/api/reactive-api.md:56-68` — the `state_hash()` API entry and the `state_hash_exclude` ClassVar block immediately below it. Same warning, API-reference register.

Both locations should carry the guidance; at minimum `docs/reactivity.md` must, with `docs/api/reactive-api.md` cross-referring rather than duplicating at length if that reads better.

### Content the edit must contain

1. **The rule.** Any field whose value is freshly generated on every render must be listed in `state_hash_exclude`.
2. **The named category**, explicitly: trace ids, request ids, and timestamps not derived from persisted data. Named categories, not a vague "ephemeral state" gesture — the existing text already says "ephemeral UI-only state" and that phrasing is what failed to convey this.
3. **The why**, in terms of observable behavior: an unexcluded per-render-random field makes `state_hash()` never repeat for that instance, which silently defeats the OOB hash gate — every parent dirty event then forces an `outerHTML` swap over every nested child region even when that child's data did not change. Silent is the operative word: nothing raises, nothing warns; the only symptom is over-swapping.
4. **The replace-not-merge gotcha.** `state_hash_exclude` is a `ClassVar[frozenset[str]]` whose subclass value *replaces* the base outright — a subclass that writes `state_hash_exclude = frozenset({"trace_id"})` has just un-excluded `id`. Correct form is `frozenset({"id", "trace_id"})`. This is documented on the ClassVar's own docstring (`component.py:61-62`) but not in the published docs, and it is the mistake a reader following this new guidance will most plausibly make.
5. Optionally a minimal example: a user-defined `ReactiveComponent` subclass with a per-render id field and the corresponding `state_hash_exclude`. Must not be a `PJX*` builtin call — `tests/pyjinhx/test_docs_reference_real_fields.py` parses every `PJXFoo(...)` call and `<PJXFoo ...>` tag in `docs/` and asserts each bare-word keyword is a declared field.

### Out of scope

- Any change to `pyjinhx/reactive/component.py`, `pyjinhx/reactive/fanout.py`, or any other source file.
- Any new tests.
- Story 1 (#1009) `hx-preserve` stamping — separate story, disjoint code path. Reference it only as the race window this guidance narrows.
- **Deferred, flag as a follow-up in the PR description, do not build:** a debug-time affordance warning when the same instance's `state_hash()` differs across back-to-back calls with otherwise-identical field values. Deferred because "otherwise identical" needs its own design pass.

## Observable behavior

No runtime behavior changes. The observable deltas are documentary:

- `docs/reactivity.md` and `docs/api/reactive-api.md` name trace/request ids and non-persisted timestamps as fields requiring exclusion, and state the over-swap consequence of omitting them.
- The replace-not-merge semantics of `state_hash_exclude` appear in published docs for the first time.
- `uv run mkdocs build --strict` continues to succeed — no broken links, no malformed markdown, no orphaned anchors introduced.

## Error paths

None at runtime. The failure modes for this change are build/lint-time:

- A broken internal link or anchor (e.g. cross-linking `reactivity.md` ↔ `api/reactive-api.md` with a wrong heading slug) fails `uv run mkdocs build --strict`.
- An example that names a `PJX*` builtin with a field it does not declare fails `tests/pyjinhx/test_docs_reference_real_fields.py`. Use a user-defined subclass in any example to stay clear of this.
- Prose that describes a *new* mechanism rather than the existing `state_hash_exclude` contradicts the milestone design and must be rejected in review.

## Tests

**No new tests.** Per the milestone spec (lines 187-189), Story 2 is a documentation change with no new test surface: the behavior it recommends — "a field in `state_hash_exclude` does not perturb the hash" — is already covered by `tests/pyjinhx/reactive/test_reactive_state_hash.py`, and the `_hash_gate_drops`/fan-out side is covered by `tests/pyjinhx/reactive/test_reactive_fanout.py` and `tests/pyjinhx/reactive/test_fanout_assets.py`. All three are unaffected by a docs-only change.

Tier note, per this repo's placement rule: there is no unit/integration/e2e taxonomy here — `tests/unit/`, `tests/integration/`, and `tests/reactivity/` are dead directories. The rule (stated at `docs/superpowers/plans/2026-08-16-issue-986.md:31` and reinforced at `docs/superpowers/plans/2026-08-16-issue-980.md:28`) is that a test file mirrors the module or feature under test. Were any test needed for this subtask it would land in `tests/pyjinhx/reactive/test_reactive_state_hash.py` (mirroring `state_hash()` in `reactive/component.py`); none is.

The existing doc-lint `tests/pyjinhx/test_docs_reference_real_fields.py` is the acceptance gate that already mirrors `docs/` and is exercised unchanged by this edit.

## Verification

- fullSuite: `uv run pytest tests/pyjinhx/`, `uv run pytest tests/`, `uv run mkdocs build --strict`, `uv run pytest tests/pyjinhx/test_docs_reference_real_fields.py -q`, `python -m build`
- typecheck: `uvx "basedpyright==1.39.9" pyjinhx/`
- lint: `ruff format .`, `ruff check .`

`uv run mkdocs build --strict` and `test_docs_reference_real_fields.py` are the two commands that actually exercise this change.

## Conventions

Docstrings explain WHAT, comments explain WHY; no PR or issue references in prose committed to `docs/`. Prefer small, human-looking prose consistent with the surrounding docs voice.
