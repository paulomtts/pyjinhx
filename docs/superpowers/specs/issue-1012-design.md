# Subtask #1012 — `record_nested_react_keys` on_rendered subscriber

Parent story: #1009 "hx-preserve retention for disjoint nested reactive regions" (milestone 18, "Nested reactive OOB ownership"). Canonical design: `docs/superpowers/specs/2026-08-23-nested-reactive-oob-preserve-design.md`, Story 1 (lines 74-227). This subtask narrows Story 1 step 1 to its first half only: build the per-request map. Nothing consumes it yet.

## Scope

Add one exported function, `record_nested_react_keys(component, level, session)`, to `pyjinhx/reactive/root_attrs.py`, placed beside `stamp_reactive_root_attrs` (currently root_attrs.py:19-52), plus the per-request map it writes into, plus tests.

Signature is fixed by the `on_rendered` callback shape: `Callable[[BaseComponent, RenderedLevel, RenderSession], None]` (`RenderSession.on_rendered`, session.py:242-244; invoked by `emit_rendered`, session.py:267-268). The two existing subscribers of that shape — `stamp_reactive_root_attrs` and `registry.register_rendered_instance` (registry.py:108-124) — are the parity references for docstring shape and for the "unused `session` argument" convention where applicable; here `session` *is* used, as the map's home.

The map's home is a new per-request attribute on `RenderSession`, declared and initialized in `__init__` alongside `css_assets`/`pjx_mounted` (session.py:206-255), suggested name `nested_react_keys: dict[str, tuple[str, ...]]`. This is the one open implementation decision the subtask body leaves to the implementer; #1013 reads whatever name lands here, so the attribute must be named clearly and carry an inline comment explaining what it holds and who consumes it. A per-request map keyed by instance id and scoped to the session is what ADR 0009 (minimal instance registry, reactivity-only) and ADR 0012 (fan-out follows the request, not the return value) require — it must not become module-global or process-lived state.

Map contents: for every `ReactiveComponent` rendered — root and nested alike — `component.id -> type(component)._pjx_react_keys` (a `tuple[str, ...]`, set per class in `__init_subclass__`, component.py:49/104). The key must be the same instance-id string that `fanout.py` resolves through `ChildRef.attrs["id"]` / `_root_instance_id(RenderedLevel)` in `_contained` (fanout.py:267-291), since that is where #1013 cross-references it.

The subtask body says the value is `_pjx_react_keys` alone. The parent story spec's step 1 describes `id -> (react_keys, load_key)`. The subtask body is authoritative for #1012: record react keys only, and flag the discrepancy explicitly in the PR description so #1013 can decide whether it needs `load_key` too.

Explicitly out of scope: any change to `pyjinhx/reactive/fanout.py` (#1013 owns `_contained`, `oob_swaps` at fanout.py:665, the `hx-preserve` splice, and the wiring that attaches this subscriber to the session `_build_dirty` uses); any change to `ReactiveComponent.retain_across_parent_swaps` (#1011, already implemented on branch `m18/task-1011`, PR #1015 — do not re-add); any auto-registration of the new subscriber.

## Observable behavior

- Exported, not auto-registered. Like `stamp_reactive_root_attrs`, callers append it to a session's `on_rendered` list explicitly. A session that never attaches it leaves the map empty; no production code path changes behavior as a result of this subtask.
- Rendering a `ReactiveComponent` with a session that has the subscriber attached leaves `session.nested_react_keys[component.id]` equal to that class's `_pjx_react_keys` tuple.
- A class declared with no `react=(...)` records the empty tuple `()` under its id — an entry is still made. Presence in the map means "this id is a reactive component"; the value answers "on what keys".
- Every reactive component in a tree gets an entry, at every nesting depth, because `emit_rendered` fires once per component. Nested entries are the point of the subtask.
- Non-reactive components are a no-op that costs one `isinstance` check and nothing else, matching the guard at root_attrs.py:37-38. No entry is written for them.
- The subscriber composes with the others: attaching it alongside `stamp_reactive_root_attrs` neither perturbs the stamped root attributes nor mutates `level` in any way. `record_nested_react_keys` performs no splice and no rendered-output mutation at all; it is read-only against `component` and `level`.
- Repeated renders in one session: a second render of the same id overwrites its entry with the same value. This is deliberately silent — unlike `registry.register_instance` (registry.py:95-105), no collision error and no warning, because the value is class-derived and idempotent.

## Error paths

There are none of its own. The function raises nothing, catches nothing, and validates nothing: `component.id` and `_pjx_react_keys` are both guaranteed present on any `ReactiveComponent`. Should it ever raise, `emit_rendered`'s comment (session.py:265-266) applies — exceptions propagate, a half-written session is not swallowed.

## Test list

Test-placement rule for this repo: tests live flat under `tests/pyjinhx/`, one file per source module named `test_<module>.py`, colocated in the matching subpackage directory. There is no unit/integration/reactivity tier split in practice (`tests/unit`, `tests/integration`, `tests/reactivity`, `tests/ui` hold no test files). So every test below goes in the single tier that exists, in `tests/pyjinhx/reactive/test_reactive_root_attrs.py`, added beside the existing `stamp_reactive_root_attrs` coverage — not in `tests/pyjinhx/reactive/test_reactive_fanout.py`, which is #1013's territory.

All tests exercise the subscriber through a real `render_level()` pass against a `RenderSession` with `record_nested_react_keys` appended to `on_rendered`, reusing the module's existing `ReactiveWidget`/`PlainWidget` fixtures and `_descriptor_for` helper.

1. A single reactive component declared with `react=("a", "b")` records `{id: ("a", "b")}` — value equality against the class's normalized `_pjx_react_keys`, not against the raw kwarg.
2. A reactive component declared with no `react` kwarg records an entry whose value is `()`; the id is present in the map.
3. A nested tree (reactive parent containing a reactive child, each with distinct `react` keys and distinct ids) records one entry per component, at both depths, with each id mapped to its own class's keys.
4. A tree of non-reactive components only leaves the map empty.
5. A mixed tree records entries for the reactive nodes only; non-reactive ids never appear as keys.
6. The recorded id matches the id `fanout` would resolve for that node — assert the map key equals the `data-pjx-id` stamped onto the level's root tag when `stamp_reactive_root_attrs` is attached to the same session, which is the identity channel `_contained` reads.
7. Composition/non-interference: with both subscribers attached, the rendered string is byte-identical to the same render with only `stamp_reactive_root_attrs` attached.
8. Isolation: two independent `RenderSession` instances rendering the same component class each hold their own map; one session's entries never appear in the other's.

## Verification

fullSuite: `uv run pytest tests/pyjinhx/ ; uv run pytest tests/ ; uv venv .venv-min && uv pip install --python .venv-min . pytest && .venv-min/bin/python -m pytest tests/minimal/ -q`

typecheck: `uvx "basedpyright==1.39.9" pyjinhx/`

lint: `ruff format . ; ruff check .`
