# Issue #1011 — declare `ReactiveComponent.retain_across_parent_swaps`

Subtask 1 of 3 under story #1009 (`hx-preserve` retention for disjoint nested reactive regions, fixes #1008), milestone 18 "Nested reactive OOB ownership". Narrows the milestone design at `docs/superpowers/specs/2026-08-23-nested-reactive-oob-preserve-design.md:110-112` to its first slice: the declaration of the opt-out flag, with nothing reading it yet.

## Scope

In scope: one new public ClassVar on `ReactiveComponent` in `pyjinhx/reactive/component.py`, plus unit tests for it.

```python
retain_across_parent_swaps: ClassVar[bool] = True
```

It is placed in the existing ClassVar block in the class body (`pyjinhx/reactive/component.py:52-67`), next to `state_hash_exclude` (line 60), which is its closest sibling in both name and role — a public, subclass-overridable knob, as opposed to the `_pjx_`-prefixed derived facts around it. It carries a short prose docstring immediately below the assignment, matching the convention of every other ClassVar in that block (docstring, not an inline comment), saying what the flag means and that a subclass sets it `False` to opt out of ever being preserved against an ancestor's OOB swap — i.e. to declare itself fully owned by its parent.

Out of scope, and explicitly owned by the sibling subtasks, which are still Backlog:

- Recording nested react-keys during dirty rebuilds — `pyjinhx/reactive/root_attrs.py` and `pyjinhx/reactive/fanout.py` (#1012).
- Reading this flag and splicing `hx-preserve="true"` in `oob_swaps()` — `pyjinhx/reactive/fanout.py` (#1013).

#1011 must not touch `root_attrs.py` or `fanout.py`. No `__init_subclass__` / `__pydantic_init_subclass__` change is needed: unlike `react=(...)` and the cache kwargs, this flag has no consumption path at class-definition time. It is a plain inherited ClassVar that a subclass overrides by reassignment in its body, exactly the mechanism `state_hash_exclude` uses.

## Observable behavior

- `ReactiveComponent.retain_across_parent_swaps` exists and is `True`.
- A subclass that says nothing inherits `True`; the value is visible on both the class and an instance.
- A subclass that assigns `retain_across_parent_swaps = False` reads back `False` on that class and its own subclasses, while `ReactiveComponent` and unrelated sibling subclasses still read `True` — the override is per-class, never a mutation of the base.
- Setting it changes no rendering, no OOB swap, no cache behavior in this subtask. The flag is inert until #1013 wires it as one of three AND-ed conditions for stamping `hx-preserve="true"` onto a nested root (react-keys disjoint from the dirtied set; the id not itself a dirty/missing candidate in the same walk; `retain_across_parent_swaps` True on the owning class).

## Error paths

None. There is no validation, no coercion, and no rejection at class-definition time — a non-bool assignment is a static typing concern only, consistent with how the neighbouring ClassVars behave. No new exception types, no new messages.

## Tests

Tier per the test-placement rule at `docs/superpowers/rebuild/implementation-overview.md:59` ("Tests mirror the package: `tests/pyjinhx/test_<module>.py` per module, `tests/pyjinhx/reactive/` for the cluster"): all of these are unit tests in the mirrored-package tree, in the existing `tests/pyjinhx/reactive/test_reactive_component.py`, beside the other `ReactiveComponent` ClassVar tests (e.g. the `_pjx_cache_policy` tests already there).

1. `retain_across_parent_swaps` defaults to `True` on `ReactiveComponent` itself — `tests/pyjinhx/reactive/test_reactive_component.py`.
2. A subclass that does not mention the flag inherits `True` — same file.
3. A subclass assigning `retain_across_parent_swaps = False` reads back `False`, and `ReactiveComponent` still reads `True` (no base mutation) — same file.
4. Two sibling subclasses set it independently: one `False`, one left alone, and each keeps its own value — same file.

Not tested here: "a nested class with `retain_across_parent_swaps = False` -> no stamp, even when keys are disjoint" (milestone spec Testing section, lines 174-177). That is Story 1's end-to-end assertion and requires the wired `oob_swaps()` behavior, so it is owned by #1013.
