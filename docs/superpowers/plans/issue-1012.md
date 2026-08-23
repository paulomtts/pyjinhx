<!-- task-pipeline: validated -->
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

---

# `record_nested_react_keys` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exported `on_rendered` subscriber that records every rendered reactive component's `id -> _pjx_react_keys` into a new per-request `RenderSession.nested_react_keys` map, so #1013 can later decide which nested reactive regions a parent swap must retain.

**Architecture:** Two source edits only. `RenderSession.__init__` gains one more per-request state slot (`nested_react_keys: dict[str, tuple[str, ...]]`), initialized empty beside `pjx_mounted`/`css_assets`. `pyjinhx/reactive/root_attrs.py` gains `record_nested_react_keys`, a sibling of `stamp_reactive_root_attrs` with the identical `(component, level, session)` callback shape and the identical `isinstance(component, ReactiveComponent)` early return; it writes one dict entry and mutates nothing else. It is exported but never auto-registered — callers append it to `session.on_rendered` themselves, exactly as `pyjinhx/integrations/fastapi.py:209` does for `stamp_reactive_root_attrs`. No `fanout.py` change, no `component.py` change.

**Tech Stack:** Python 3.12+, Pydantic-based `BaseComponent`, pytest, `uv`, ruff, basedpyright.

**Spec:** `docs/superpowers/specs/issue-1012-design.md` (reproduced verbatim above this plan).

## Global Constraints

- Branch `m18/task-1012` in worktree `/home/mtts/Code/libs/pyjinhx/.claude/worktrees/m18/task-1012`, cut from `origin/m18/task-1011`. Assume no other subtask's code exists here beyond that base.
- Do **not** touch `pyjinhx/reactive/fanout.py`. `_contained` (fanout.py:267-291) and `oob_swaps` (fanout.py:665) belong to #1013.
- Do **not** add, remove, or edit `ReactiveComponent.retain_across_parent_swaps`. It belongs to #1011 and is already on the base branch.
- Do **not** auto-register the new subscriber anywhere (not in `pyjinhx/integrations/fastapi.py`, not in `pyjinhx/reactive/fanout.py`). Export only.
- New session attribute name is exactly `nested_react_keys`, typed exactly `dict[str, tuple[str, ...]]`. #1013 reads this name.
- Map value is `type(component)._pjx_react_keys` alone. Do **not** add `load_key`, even though the parent story spec mentions it; instead flag the discrepancy in the PR description (Task 5).
- Request-scoped state only: the map lives on the `RenderSession` instance. No module-level dict, no `ContextVar`, no class attribute (ADR 0009, ADR 0012).
- All new tests go in `tests/pyjinhx/reactive/test_reactive_root_attrs.py` — the repo's single de facto test tier, one test file per source module colocated in the matching subpackage directory.
- Verification commands, each run as its own invocation, never chained with `&&`:
  - `uv run pytest tests/pyjinhx/`
  - `uv run pytest tests/`
  - `uv venv .venv-min && uv pip install --python .venv-min . pytest && .venv-min/bin/python -m pytest tests/minimal/ -q`
  - `uvx "basedpyright==1.39.9" pyjinhx/`
  - `ruff format .`
  - `ruff check .`

---

### Task 1: The per-request map on `RenderSession`

**Files:**
- Modify: `pyjinhx/session.py:255` (end of `RenderSession.__init__`, right after `self.pjx_trigger`)
- Test: `tests/pyjinhx/reactive/test_reactive_root_attrs.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RenderSession.nested_react_keys: dict[str, tuple[str, ...]]` — empty dict on a fresh session, one per instance. Task 2 writes into it; #1013 reads it.

- [ ] **Step 1: Write the failing test**

Append at the end of `tests/pyjinhx/reactive/test_reactive_root_attrs.py`:

```python
def test_fresh_session_starts_with_an_empty_nested_react_keys_map():
    """#1012's per-request map: empty until a subscriber writes into it."""
    assert RenderSession().nested_react_keys == {}


def test_each_session_owns_its_own_nested_react_keys_map():
    """Per-request by construction: no shared class-level or module-level dict."""
    first = RenderSession()
    second = RenderSession()

    first.nested_react_keys["w"] = ("a",)

    assert second.nested_react_keys == {}
    assert first.nested_react_keys is not second.nested_react_keys
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -k nested_react_keys_map -v`
Expected: FAIL, both tests, with `AttributeError: 'RenderSession' object has no attribute 'nested_react_keys'`.

- [ ] **Step 3: Write the minimal implementation**

In `pyjinhx/session.py`, in `RenderSession.__init__`, immediately after the `self.pjx_trigger: dict[str, Any] | None = None` line (session.py:255):

```python
        # Per-request map of reactive instance id -> that class's
        # _pjx_react_keys, written by reactive.root_attrs.record_nested_react_keys
        # when a caller appends it to on_rendered above. #1013's fan-out reads it
        # to decide which nested reactive regions a parent swap must retain, so
        # the key is the same instance-id string fanout's _contained resolves
        # (ChildRef.attrs["id"] / _root_instance_id). Lives on the session, not
        # module-global: it must die with the request.
        self.nested_react_keys: dict[str, tuple[str, ...]] = {}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -k nested_react_keys_map -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pyjinhx/session.py tests/pyjinhx/reactive/test_reactive_root_attrs.py
git commit -m "feat: add per-request RenderSession.nested_react_keys map"
```

---

### Task 2: `record_nested_react_keys` records reactive components

**Files:**
- Modify: `pyjinhx/reactive/root_attrs.py` (append after `stamp_reactive_root_attrs`, which ends at root_attrs.py:52)
- Test: `tests/pyjinhx/reactive/test_reactive_root_attrs.py`

**Interfaces:**
- Consumes: `RenderSession.nested_react_keys: dict[str, tuple[str, ...]]` from Task 1.
- Produces: `record_nested_react_keys(component: BaseComponent, level: RenderedLevel, session: RenderSession) -> None` — an `on_rendered`-shaped subscriber, exported from `pyjinhx.reactive.root_attrs`, never auto-registered.

- [ ] **Step 1: Add the test fixtures this task and Tasks 3-4 need**

In `tests/pyjinhx/reactive/test_reactive_root_attrs.py`, add these class definitions and descriptors immediately after the `ReactiveShell.__pjx_descriptor__ = ClassDescriptor(...)` block (currently test file lines 81-89):

```python
class KeyedReactiveWidget(ReactiveComponent, react=("a", "b")):
    pass


class UnkeyedReactiveWidget(ReactiveComponent):
    pass


class KeyedReactiveShell(ReactiveComponent, react=("shell",)):
    body: Slot = ""


class PlainShell(BaseComponent):
    body: Slot = ""


KeyedReactiveWidget.__pjx_descriptor__ = _descriptor_for(
    KeyedReactiveWidget, "reactive_widget.html"
)
UnkeyedReactiveWidget.__pjx_descriptor__ = _descriptor_for(
    UnkeyedReactiveWidget, "reactive_widget.html"
)
KeyedReactiveShell.__pjx_descriptor__ = ClassDescriptor(
    template_path=_TEMPLATE_DIR / "reactive_shell.html",
    slot_fields=frozenset({"body"}),
    children_field=None,
    css_paths=(),
    js_paths=(),
    strict=True,
    provenance={"template": KeyedReactiveShell},
)
PlainShell.__pjx_descriptor__ = ClassDescriptor(
    template_path=_TEMPLATE_DIR / "reactive_shell.html",
    slot_fields=frozenset({"body"}),
    children_field=None,
    css_paths=(),
    js_paths=(),
    strict=True,
    provenance={"template": PlainShell},
)
```

Then add this fixture immediately after the existing `session` fixture (test file lines 154-159):

```python
@pytest.fixture
def recording_session() -> RenderSession:
    """A session with only the nested-react-keys recorder attached."""
    session = RenderSession()
    session.on_rendered.append(record_nested_react_keys)
    return session
```

And extend the existing import at test file line 18 to:

```python
from pyjinhx.reactive.root_attrs import (
    record_nested_react_keys,
    stamp_reactive_root_attrs,
)
```

- [ ] **Step 2: Write the failing tests**

Append at the end of `tests/pyjinhx/reactive/test_reactive_root_attrs.py`:

```python
def test_records_a_reactive_components_declared_react_keys(
    recording_session: RenderSession,
):
    """Spec test 1: the value is the class's normalized _pjx_react_keys tuple."""
    component = KeyedReactiveWidget(id="k1")

    render_level(component, recording_session)

    assert recording_session.nested_react_keys == {
        "k1": KeyedReactiveWidget._pjx_react_keys
    }
    assert recording_session.nested_react_keys["k1"] == ("a", "b")


def test_reactive_component_without_react_kwarg_records_an_empty_tuple(
    recording_session: RenderSession,
):
    """Spec test 2: presence means 'reactive'; the value answers 'on what keys'."""
    render_level(UnkeyedReactiveWidget(id="u1"), recording_session)

    assert "u1" in recording_session.nested_react_keys
    assert recording_session.nested_react_keys["u1"] == ()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -k "records_a_reactive_components_declared or without_react_kwarg" -v`
Expected: FAIL at collection/import time with `ImportError: cannot import name 'record_nested_react_keys' from 'pyjinhx.reactive.root_attrs'`.

- [ ] **Step 4: Write the minimal implementation**

Append to `pyjinhx/reactive/root_attrs.py`, after `stamp_reactive_root_attrs` (which ends at root_attrs.py:52):

```python
def record_nested_react_keys(
    component: BaseComponent, level: RenderedLevel, session: RenderSession
) -> None:
    """Record a rendered reactive component's react keys under its instance id."""
    session.nested_react_keys[component.id] = type(component)._pjx_react_keys  # pyright: ignore[reportAttributeAccessIssue]
```

Note: this deliberately has no `isinstance` guard yet and carries a temporary pyright suppression — Task 3 adds the guard and removes the suppression. Do not run the typecheck command against this intermediate state.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -k "records_a_reactive_components_declared or without_react_kwarg" -v`
Expected: PASS, 2 passed.

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/reactive/root_attrs.py tests/pyjinhx/reactive/test_reactive_root_attrs.py
git commit -m "feat: record reactive components' react keys on the render session"
```

---

### Task 3: Non-reactive components are a no-op

**Files:**
- Modify: `pyjinhx/reactive/root_attrs.py` (the `record_nested_react_keys` body added in Task 2)
- Test: `tests/pyjinhx/reactive/test_reactive_root_attrs.py`

**Interfaces:**
- Consumes: `record_nested_react_keys(component, level, session)` from Task 2; the `recording_session` fixture and the `PlainShell` / `KeyedReactiveShell` fixtures from Task 2 Step 1.
- Produces: the final shape of `record_nested_react_keys` — an `isinstance(component, ReactiveComponent)` early return before any read, mirroring `stamp_reactive_root_attrs` (root_attrs.py:38-39), so a non-reactive tree pays one isinstance check per component and nothing else.

- [ ] **Step 1: Write the failing tests**

Append at the end of `tests/pyjinhx/reactive/test_reactive_root_attrs.py`:

```python
def test_a_tree_of_plain_components_records_nothing(
    recording_session: RenderSession,
):
    """Spec test 4: non-reactive components are a bare isinstance no-op."""
    render_level(PlainShell(id="ps1", body=PlainWidget(id="pw1")), recording_session)

    assert recording_session.nested_react_keys == {}


def test_a_mixed_tree_records_only_its_reactive_nodes(
    recording_session: RenderSession,
):
    """Spec test 5: a plain child of a reactive parent never becomes a key."""
    render_level(
        KeyedReactiveShell(id="mix1", body=PlainWidget(id="plain1")),
        recording_session,
    )

    assert recording_session.nested_react_keys == {"mix1": ("shell",)}
    assert "plain1" not in recording_session.nested_react_keys
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -k "tree_of_plain_components or mixed_tree_records" -v`
Expected: FAIL, both tests, with `AttributeError: type object 'PlainWidget' has no attribute '_pjx_react_keys'` (raised out of `emit_rendered`, which lets subscriber exceptions propagate).

- [ ] **Step 3: Write the implementation**

Replace the whole `record_nested_react_keys` body in `pyjinhx/reactive/root_attrs.py` with the final version, guard and full docstring included:

```python
def record_nested_react_keys(
    component: BaseComponent, level: RenderedLevel, session: RenderSession
) -> None:
    """Record a rendered reactive component's react keys under its instance id.

    Shaped for ``RenderSession.on_rendered`` and exported rather than
    auto-registered: a session that never appends it keeps an empty
    ``nested_react_keys`` map, so nothing in a normal render changes. A
    non-reactive component returns before anything is read, so a tree with no
    reactive nodes pays one isinstance check per component and nothing else.

    ``emit_rendered`` fires once per component, so every reactive node lands an
    entry at every nesting depth — the nested entries are what #1013's fan-out
    needs to tell a disjoint nested reactive region from part of a parent's own
    swap. A class declared without ``react=(...)`` records the empty tuple:
    presence of an id means "this is a reactive component", the value answers
    "on what keys". A repeat render of one id overwrites in silence — unlike
    ``registry.register_instance``, there is nothing to collide over, since the
    value is class-derived and every write for one id is identical.

    Args:
        component: The component that just finished rendering.
        level: That component's RenderedLevel (unused; this subscriber splices
            nothing and leaves the rendered output byte-identical).
        session: The RenderSession this render ran against; its
            ``nested_react_keys`` map is where the entry lands.
    """
    if not isinstance(component, ReactiveComponent):
        return
    session.nested_react_keys[component.id] = type(component)._pjx_react_keys
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -k "tree_of_plain_components or mixed_tree_records" -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Run the whole module's tests to verify nothing regressed**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -v`
Expected: PASS, all tests including the pre-existing `stamp_reactive_root_attrs` suite.

- [ ] **Step 6: Commit**

```bash
git add pyjinhx/reactive/root_attrs.py tests/pyjinhx/reactive/test_reactive_root_attrs.py
git commit -m "feat: skip non-reactive components in record_nested_react_keys"
```

---

### Task 4: Lock in nesting, identity, composition and isolation

**Files:**
- Test: `tests/pyjinhx/reactive/test_reactive_root_attrs.py`

**Interfaces:**
- Consumes: the final `record_nested_react_keys` from Task 3; the `session` fixture (only `stamp_reactive_root_attrs` attached), the `recording_session` fixture, and the `KeyedReactiveWidget` / `KeyedReactiveShell` fixtures.
- Produces: nothing new in `pyjinhx/`. These are the four remaining spec behaviors (spec tests 3, 6, 7, 8) that the Task 2/3 implementation already satisfies; they exist so #1013 cannot silently break them.

**Important:** these tests must pass on their first run with **no** change to `pyjinhx/`. If one fails, that is a real defect in Task 2/3's implementation — stop, use `superpowers:systematic-debugging`, and fix the source rather than weakening the test.

- [ ] **Step 1: Write the tests**

Append at the end of `tests/pyjinhx/reactive/test_reactive_root_attrs.py`:

```python
def test_every_depth_of_a_nested_reactive_tree_gets_its_own_entry(
    recording_session: RenderSession,
):
    """Spec test 3: nested entries are the point — one per component, per class."""
    child = KeyedReactiveWidget(id="inner-k")
    parent = KeyedReactiveShell(id="outer-k", body=child)

    render_level(parent, recording_session)

    assert recording_session.nested_react_keys == {
        "outer-k": ("shell",),
        "inner-k": ("a", "b"),
    }


def test_the_recorded_id_is_the_id_stamped_as_data_pjx_id():
    """Spec test 6: the map key is the identity channel fanout's _contained reads."""
    both = RenderSession()
    both.on_rendered.append(stamp_reactive_root_attrs)
    both.on_rendered.append(record_nested_react_keys)

    html = serialize(render_level(KeyedReactiveWidget(id="ident1"), both))

    assert list(both.nested_react_keys) == ["ident1"]
    assert 'data-pjx-id="ident1"' in html


def test_recording_leaves_the_rendered_markup_byte_identical():
    """Spec test 7: the recorder splices nothing and perturbs no other stamp."""
    stamp_only = RenderSession()
    stamp_only.on_rendered.append(stamp_reactive_root_attrs)
    both = RenderSession()
    both.on_rendered.append(stamp_reactive_root_attrs)
    both.on_rendered.append(record_nested_react_keys)

    without = serialize(
        render_level(
            KeyedReactiveShell(id="bytes1", body=KeyedReactiveWidget(id="bytes2")),
            stamp_only,
        )
    )
    with_recorder = serialize(
        render_level(
            KeyedReactiveShell(id="bytes1", body=KeyedReactiveWidget(id="bytes2")),
            both,
        )
    )

    assert with_recorder == without
    assert both.nested_react_keys == {"bytes1": ("shell",), "bytes2": ("a", "b")}
    assert stamp_only.nested_react_keys == {}


def test_two_sessions_never_see_each_others_entries():
    """Spec test 8: request-scoped state, per ADR 0009/0012."""
    first = RenderSession()
    first.on_rendered.append(record_nested_react_keys)
    second = RenderSession()
    second.on_rendered.append(record_nested_react_keys)

    render_level(KeyedReactiveWidget(id="s1"), first)
    render_level(KeyedReactiveWidget(id="s2"), second)

    assert first.nested_react_keys == {"s1": ("a", "b")}
    assert second.nested_react_keys == {"s2": ("a", "b")}
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_root_attrs.py -k "every_depth_of_a_nested or recorded_id_is_the_id or byte_identical or two_sessions_never" -v`
Expected: PASS, 4 passed, with no edit to `pyjinhx/`.

- [ ] **Step 3: Commit**

```bash
git add tests/pyjinhx/reactive/test_reactive_root_attrs.py
git commit -m "test: lock nesting, identity, composition and session isolation for record_nested_react_keys"
```

---

### Task 5: Full verification and PR note

**Files:**
- Modify (only if `ruff format` rewrites them): `pyjinhx/session.py`, `pyjinhx/reactive/root_attrs.py`, `tests/pyjinhx/reactive/test_reactive_root_attrs.py`

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: a clean tree against all five verification commands, plus the PR-description paragraph flagging the `load_key` scope discrepancy.

- [ ] **Step 1: Confirm no out-of-scope file changed**

Run: `git diff --stat origin/m18/task-1011...HEAD`
Expected: exactly three files — `pyjinhx/session.py`, `pyjinhx/reactive/root_attrs.py`, `tests/pyjinhx/reactive/test_reactive_root_attrs.py`. If `pyjinhx/reactive/fanout.py` or `pyjinhx/reactive/component.py` appears, revert that file: it belongs to #1013 / #1011.

- [ ] **Step 2: Format**

Run: `ruff format .`
Expected: reports only the files above as reformatted, or "0 files reformatted".

- [ ] **Step 3: Lint**

Run: `ruff check .`
Expected: "All checks passed!".

- [ ] **Step 4: Typecheck**

Run: `uvx "basedpyright==1.39.9" pyjinhx/`
Expected: 0 errors. In particular the temporary `# pyright: ignore[reportAttributeAccessIssue]` from Task 2 Step 4 must be gone (Task 3 Step 3 replaced that line); if basedpyright reports an unnecessary-ignore, delete the leftover comment.

- [ ] **Step 5: Run tier 1**

Run: `uv run pytest tests/pyjinhx/`
Expected: PASS, no failures.

- [ ] **Step 6: Run tier 2**

Run: `uv run pytest tests/`
Expected: PASS, no failures.

- [ ] **Step 7: Run tier 3 (minimal-install suite)**

Run: `uv venv .venv-min && uv pip install --python .venv-min . pytest && .venv-min/bin/python -m pytest tests/minimal/ -q`
Expected: PASS, no failures.

- [ ] **Step 8: Commit any formatting fallout**

```bash
git add -A
git commit -m "chore: ruff format after record_nested_react_keys" || echo "nothing to commit"
```

- [ ] **Step 9: Record the PR-description note**

Include this paragraph verbatim in the PR body when the PR for #1012 is opened:

```markdown
**Scope note for #1013:** the subtask body for #1012 specifies the per-request
map's value as `_pjx_react_keys` alone, while the parent story spec
(`docs/superpowers/specs/2026-08-23-nested-reactive-oob-preserve-design.md`,
Story 1 step 1) describes `id -> (react_keys, load_key)`. This PR follows the
subtask body and records react keys only. If #1013's `_contained`
cross-reference turns out to need the load key too, widening
`RenderSession.nested_react_keys`' value type is a one-line change in
`record_nested_react_keys` — flagging it here rather than pre-building it.

**Consumed by #1013:** the attribute name is `RenderSession.nested_react_keys`,
typed `dict[str, tuple[str, ...]]`, keyed by the same instance-id string
`fanout._contained` resolves via `ChildRef.attrs["id"]` / `_root_instance_id`.
The subscriber is exported and **not** auto-registered: #1013 must append
`record_nested_react_keys` to the session `_build_dirty` uses.
```
