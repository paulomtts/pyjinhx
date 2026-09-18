<!-- task-pipeline: validated -->
<!-- SPEC (verbatim copy of docs/superpowers/specs/issue-1024-design.md) -->

# Quiet expected registry collisions during the fan-out build pass (subtask #1024)

Narrows the agreed design in `docs/superpowers/specs/issue-1022.md` (story #1023) to one subtask. Nothing here re-argues that design; it fixes the surface, the boundaries and the tests.

## Scope

Four source touches plus two doc/comment touches:

1. `pyjinhx/session.py` — one new request-scoped `ContextVar` holding a set of composite keys whose collisions are expected, a sibling of `_instances` (session.py:33-35), plus a getter mirroring `get_instances()` (session.py:312-318) and a setter/mutator so `registry.py` can read and write it without importing anything new. It is set and reset in `request_scope()` alongside `_instances` (session.py:448 and session.py:469), by token, in the same order discipline as the existing pairs.
2. `pyjinhx/registry.py` — `quiet_collisions(keys: Iterable[str])`, a context manager that adds those composite keys to the request's quiet set for the duration of the block and restores the previous set on exit (including on exception).
3. `pyjinhx/registry.py` — `register_instance`'s collision branch (registry.py:95-105) consults the quiet set before it raises `InstanceKeyCollisionError` under `get_dev_strict()` or logs `"Key %r is already registered; overwriting."`.
4. `pyjinhx/reactive/fanout.py` — `_build_one` (fanout.py:520-534) wraps its `_build_dirty(...)` call in `quiet_collisions(...)` over the composite keys of every *other* item in the pass's item list; `_build_pass` (fanout.py:537-593) computes that key set once, before any build starts, from `_filter_pass`'s `items` (fanout.py:451-503) and hands it to `_build_one`.
5. `pyjinhx/session.py:26` — the `# The eight pieces of per-request mutable state` comment becomes nine (or is reworded to drop the count).
6. `docs/superpowers/rebuild/architecture-overview.md:167` — invariant 4's enumerated per-request census gains the quiet-collisions set, per that line's own rule that "a mechanism needing mutable state not in this census amends this census first."

Opportunistic, one line, not blocking: `register_rendered_instance`'s docstring (registry.py:113-115) says it is "subscribed by no production code", which is stale — `pyjinhx/integrations/fastapi.py:210` wires it onto every request's session. Correct the sentence; do not expand beyond it.

## Observable behavior

- A second `register_instance` write to a composite key that is in the request's quiet set: the entry is overwritten (last-write-wins, unchanged), no warning is logged, and no `InstanceKeyCollisionError` is raised even with `get_dev_strict()` true.
- A second write to a key **not** in the quiet set: unchanged from today — raises `InstanceKeyCollisionError` under dev-strict, else logs `"Key %r is already registered; overwriting."` at WARNING and overwrites.
- Item `X`'s own composite key is excluded from the set quieted during `X`'s build. A collision on `X`'s own key is not the benign nested-duplicate shape and must warn/raise exactly as today.
- The quiet set is empty outside `quiet_collisions`, empty outside `request_scope()`, and does not leak from one `request_scope()` into another or from an inner scope back to an outer one.
- `quiet_collisions` behaves identically on both `_build_pass` branches: the inline all-cheap branch (fanout.py:586-587), which runs on the caller's own ContextVars, and the `ThreadPoolExecutor` branch (fanout.py:588-593), where each item's `copy_context().run(...)` copy must see the request's quiet set. Because the context manager is entered *inside* `_build_one` (i.e. inside the worker's copied context), a worker's enter/exit cannot disturb a sibling worker's or the submitting thread's view.
- End-to-end: a request whose manifest lists both a parent candidate and a child candidate that is a nested descendant of the parent's tree produces no "already registered; overwriting" warning and no dev-strict crash, while `_drop_nested`'s output filtering, the shipped swap set and the number of renders performed are all bit-for-bit unchanged.
- Registration performed outside `request_scope()` still takes the existing early-return "dropped" path (registry.py:90-94) before any quiet-set check.

## Error paths

- `quiet_collisions` used outside an active `request_scope()`: it must not raise. The mechanism is advisory noise-suppression, and `register_instance` already handles the out-of-scope case by dropping the write with a warning. Whether the quiet set is a throwaway there (the `get_instances()` shape) or the manager is a no-op is an implementation choice; the observable requirement is "no new exception type, no new failure mode".
- An exception raised inside a `quiet_collisions` block — including the `LookupError` `_build_one` catches as ADR 0013's proof of absence, and any other exception `_build_pass` deliberately lets travel — must restore the prior quiet set on the way out. `_build_pass`'s all-or-nothing behavior against non-`LookupError` exceptions is unchanged.
- Nested `quiet_collisions` blocks must compose (inner set unions with outer, exit restores the outer exactly). Not exercised by the current fan-out wiring, but required so the mechanism cannot strand state.
- No new public exception type. `InstanceKeyCollisionError` keeps its meaning and its message.

## Non-goals

Carried verbatim from the story's Non-goals; the subtask is bounded by them:

- Do not eliminate the redundant render/load itself. Doing that needs a client-reported parent/child manifest relationship that `client/pjx.js` does not send; explicitly deferred to a follow-up.
- Do not change `_drop_nested` or any containment-based output filtering.
- Do not change last-write-wins for a genuine race.
- No `client/pjx.js` change, no manifest-shape change.
- Do not weaken the genuine-authoring-bug case: two unrelated top-level components sharing a hard-coded id, neither nested in the other, still warn and still raise.

## Layering constraint

Zero new edges in `tests/pyjinhx/test_import_graph.py`'s `ALLOWED_INTERNAL_IMPORTS`. `reactive.fanout` already declares `pyjinhx.registry` and `pyjinhx.session` (test_import_graph.py:566-580); `registry` already declares `pyjinhx.session` (test_import_graph.py:593). The new ContextVar therefore lives in `session.py` and is reached from `registry.py` exactly the way `get_dev_strict()` and `get_instances()` already are. `registry.py` must not import `pyjinhx.dev` in any form, including function-locally — the rule pinned by `docs/superpowers/notes/2026-08-16-issue-985-registry-id-collision.md`'s "Mechanism" section.

The new state is per-request (one manifest walk's quiet set), so it is a `ContextVar` like `_instances` — **not** a lock-guarded module global like `_dev_strict` (session.py:51-59), which is process-wide configuration and deliberately outside invariant 4's census. Do not conflate the two patterns.

## Test list

Tier per the repo's two-tier convention: **per-module** tests hand-enter `request_scope()` / build a `RenderSession` and wire `on_rendered` themselves; **end-to-end** tests never enter a scope by hand and only drive a real `fastapi.testclient.TestClient` through `apply_setup` middleware.

Per-module, `tests/pyjinhx/test_instance_registry.py` (registry semantics, direct `register_instance` calls under a hand-entered scope):

1. A second `register_instance` on a key inside `quiet_collisions` logs no warning and leaves the last value in the registry.
2. A second `register_instance` on a key *outside* the quiet set still logs `"already registered; overwriting"` while some other key is quieted.
3. With `dev` strict mode on, a quieted key does not raise `InstanceKeyCollisionError`; an unquieted one in the same scope still does.
4. After the `quiet_collisions` block exits, the same key collides loudly again.
5. The quiet set does not survive `request_scope()` exit: a fresh scope starts empty, and an inner scope's quiet set does not leak into the outer scope after it exits.
6. `quiet_collisions` restores the previous quiet set when the block body raises.
7. `quiet_collisions` outside `request_scope()` raises nothing, and `register_instance` there still takes its existing "registered outside request_scope(); dropped" path.

Per-module, `tests/pyjinhx/reactive/test_reactive_fanout.py` (the manifest-walk unit tier — build a session, wire `register_rendered_instance` onto `on_rendered` as `integrations/fastapi.py:208-210` does, drive `walk_manifest`):

8. Parent candidate whose template nests a child via a `ChildRef` tag, with the child also reported as its own top-level manifest entry and both matching the request's dirtied keys: no "already registered; overwriting" warning is emitted.
9. Same scenario with dev-strict on: no `InstanceKeyCollisionError` escapes `walk_manifest`.
10. Same scenario: the surviving candidate list and shipped swaps are unchanged from the pre-change expectation — `_drop_nested` still drops the nested candidate.
11. Two *unrelated* top-level candidates colliding on a hard-coded id, neither nested in the other, still warn and still raise under dev-strict — the quieting does not mask the authoring bug.
12. The quieting holds on the inline branch too: a pass whose every class is measured too-cheap-to-thread (so `_build_pass` never touches the pool) shows the same suppression as the threaded branch, and the threaded branch is covered by the scenarios above.

End-to-end, `tests/pyjinhx/integrations/test_reactive_request_cycle.py`:

13. One `TestClient` reactive request through `apply_setup` whose `X-PJX-Mounted` manifest lists both the parent and its nested child: the response is a normal 200 with the expected OOB swaps and the request emits no registry collision warning. One test only — the tier exists to prove the production `on_rendered` wiring reaches the new path, not to re-cover the matrix above.

Structural, `tests/pyjinhx/test_import_graph.py`: no new entries. The existing graph assertions must pass untouched; if they need an edit, the wiring took the wrong shape.

<!-- END SPEC -->

---

# Quiet Expected Registry Collisions During the Fan-Out Build Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fan-out build that re-renders a component already rendered as a nested descendant of a sibling candidate's tree stops logging "already registered; overwriting" and stops crashing dev-strict mode, without changing which swap ships, which entry wins, or how many renders run.

**Architecture:** One new request-scoped `ContextVar` in `pyjinhx/session.py` holds a frozenset of composite keys whose collision is expected. `pyjinhx/registry.py` gains a `quiet_collisions(keys)` context manager that unions keys into that set (restoring the previous set by token on exit, including on exception) and a one-clause gate in `register_instance`'s collision branch that skips both the warning and the dev-strict raise for a quieted key while still overwriting. `pyjinhx/reactive/fanout.py`'s `_build_pass` computes every work item's composite key once, before any build starts, and hands that frozenset to `_build_one`, which subtracts its own item's key and opens the quiet block around `_build_dirty`.

**Tech Stack:** Python 3.11+, `contextvars`, `contextlib.contextmanager`, pytest (with `caplog`), FastAPI `TestClient`, uv, ruff, basedpyright.

**Spec:** `docs/superpowers/specs/issue-1024-design.md` (reproduced verbatim above). Parent design: `docs/superpowers/specs/issue-1022.md`.

## Global Constraints

- Branch `m18/task-1024`, worktree `/home/mtts/Code/libs/pyjinhx/.claude/worktrees/m18/task-1024`, cut fresh from `origin/master`. No other subtask's code exists on this branch; every file:line reference below is against `origin/master`.
- Zero new entries in `tests/pyjinhx/test_import_graph.py`'s `ALLOWED_INTERNAL_IMPORTS`. `reactive.fanout` already declares `pyjinhx.registry` and `pyjinhx.session`; `registry` already declares `pyjinhx.session`. If that file needs an edit, the wiring took the wrong shape — stop and rethink.
- `pyjinhx/registry.py` must not import `pyjinhx.dev` in any form, including function-locally (`docs/superpowers/notes/2026-08-16-issue-985-registry-id-collision.md`, "Mechanism").
- The new state is a `ContextVar` like `_instances`, **not** a lock-guarded module global like `_dev_strict`.
- Item `X`'s own composite key is excluded from the set quieted during `X`'s build. Known and accepted narrowing: this fixes the ordering the #1022 trace reports (the item's own dedicated build writes first, the sibling's *nested* re-render collides second). The reverse ordering — the nested write landing first, the item's own write second — still warns, by design, because that is the same shape as the genuine hard-coded-id bug. Every test below is written so the ordering under test is deterministic.
- Do not change `_drop_nested`, last-write-wins, `client/pjx.js`, or the manifest shape. Do not attempt to eliminate the redundant render itself.
- No new public exception type; `InstanceKeyCollisionError`'s message is unchanged.
- Docs touched are exactly two: the `session.py:26` count comment and `docs/superpowers/rebuild/architecture-overview.md:167`. `docs/api/registry.md` is deliberately **not** touched — `quiet_collisions` is internal fan-out wiring, and `tests/pyjinhx/test_docs_api_boundary.py` enumerates a fixed symbol list that does not include it.

**Verification commands (each in its own invocation — never chained with `&&`):**

```bash
uv run playwright install --with-deps chromium
```

```bash
uv run pytest tests/pyjinhx/
```

```bash
uv run pytest tests/
```

```bash
uvx "basedpyright==1.39.9" pyjinhx/
```

```bash
ruff format .
```

```bash
ruff check .
```

## File Structure

| File | Change | Responsibility |
| --- | --- | --- |
| `pyjinhx/session.py` | Modify (26, after 49, after 318, 453/464) | Owns the new `_quiet_collisions` ContextVar, its `get_quiet_collisions()` reader, and its per-scope bind/reset. |
| `pyjinhx/registry.py` | Modify (9-12, 95-105, 113-115) | Owns `quiet_collisions()` and the collision-branch gate. |
| `pyjinhx/reactive/fanout.py` | Modify (520-534, 583-593) | Computes the pass's key set once and opens the quiet block per item. |
| `scripts/bench_reactive_fanout.py` | Modify (322-328) | Direct `_build_one` caller; must follow the new signature (exercised by `tests/test_bench_scripts_smoke.py`). |
| `docs/superpowers/rebuild/architecture-overview.md` | Modify (167) | Invariant-4 per-request mutable-state census. |
| `tests/pyjinhx/test_instance_registry.py` | Modify (append) | Per-module tier: registry semantics under a hand-entered scope (spec tests 1-7). |
| `tests/pyjinhx/reactive/test_reactive_fanout.py` | Modify (imports, fixture, append) | Per-module tier: the manifest walk with `on_rendered` wired by hand (spec tests 8-12). |
| `tests/pyjinhx/integrations/test_reactive_request_cycle.py` | Modify (imports, classes, fixture, append) | End-to-end tier: one real `TestClient` request through `apply_setup` (spec test 13). |
| `tests/templates/cycle_shell.pjx` | Create | E2E parent template nesting the child by `ChildRef` tag. |
| `tests/templates/cycle_nested.pjx` | Create | E2E child template. |

---

### Task 1: The request-scoped quiet set, `quiet_collisions()`, and the collision gate

**Files:**
- Modify: `pyjinhx/session.py:26`, `pyjinhx/session.py:47-49` (append after), `pyjinhx/session.py:312-318` (append after), `pyjinhx/session.py:453`, `pyjinhx/session.py:464`
- Modify: `pyjinhx/registry.py:9-12`, `pyjinhx/registry.py:95-105`
- Modify: `docs/superpowers/rebuild/architecture-overview.md:167`
- Test: `tests/pyjinhx/test_instance_registry.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `pyjinhx.session._quiet_collisions: ContextVar[frozenset[str] | None]` (default `None`)
  - `pyjinhx.session.get_quiet_collisions() -> frozenset[str]`
  - `pyjinhx.registry.quiet_collisions(keys: Iterable[str]) -> Iterator[None]` (a `@contextmanager`, used as `with quiet_collisions([...]):`)
  - `pyjinhx.registry.register_instance(type_name: str, instance_id: str, entry: object) -> None` — signature unchanged, behavior gated.

- [ ] **Step 1: Write the failing test — a quieted key collides silently and still last-write-wins**

In `tests/pyjinhx/test_instance_registry.py`, extend the existing `pyjinhx.registry` import block (currently lines 11-17) to pull in the new manager, and extend the existing `pyjinhx.session` import (line 20) with the new getter:

```python
from pyjinhx.registry import (
    InstanceKeyCollisionError,
    make_key,
    quiet_collisions,
    register_instance,
    register_rendered_instance,
    resolve,
)
from pyjinhx.rendering import render_level
from pyjinhx.segments import RenderedLevel, serialize
from pyjinhx.session import (
    RenderSession,
    _instances,
    get_instances,
    get_quiet_collisions,
    request_scope,
)
```

Then append this test at the end of the file:

```python
def test_a_quieted_key_collides_silently_and_still_last_write_wins(caplog):
    """The #1022 shape: the collision is expected, so only the log and the raise go."""
    second = Widget("second")
    with request_scope(), caplog.at_level(logging.WARNING, logger="pyjinhx"):
        register_instance("Widget", "w1", Widget("first"))
        with quiet_collisions([make_key("Widget", "w1")]):
            register_instance("Widget", "w1", second)
        assert caplog.records == []
        # Last-write-wins is untouched: quieting suppresses the noise, never
        # the overwrite.
        assert resolve("Widget", "w1") is second
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/pyjinhx/test_instance_registry.py::test_a_quieted_key_collides_silently_and_still_last_write_wins -v`
Expected: FAIL at collection with `ImportError: cannot import name 'quiet_collisions' from 'pyjinhx.registry'`.

- [ ] **Step 3: Add the ContextVar, its getter, and its per-scope bind/reset in `pyjinhx/session.py`**

Change the census comment at line 26 from "eight" to "nine":

```python
# The nine pieces of per-request mutable state. They live here rather than
```

Add the ContextVar immediately after the `_freshness_cache` block (session.py:47-49), before the `_dev_strict` comment block:

```python
_quiet_collisions: ContextVar[frozenset[str] | None] = ContextVar(
    "pjx_quiet_collisions", default=None
)
```

Add the reader immediately after `get_instances()` (session.py:312-318):

```python
def get_quiet_collisions() -> frozenset[str]:
    """Return the composite keys whose collision is expected, empty outside a scope.

    A key in this set is one some caller already knows two writers will claim in
    this request, so register_instance() overwrites without the warning or the
    dev-strict raise. Empty is the normal answer: the set is only non-empty
    inside a registry.quiet_collisions() block.
    """
    quiet = _quiet_collisions.get()
    if quiet is None:
        return frozenset()
    return quiet
```

In `request_scope()`, bind it after `freshness_token` (session.py:453):

```python
    freshness_token = _freshness_cache.set({})
    quiet_token = _quiet_collisions.set(frozenset())
```

and reset it first among that group in the `finally` block, immediately after the `load_token` branch (session.py:462-464):

```python
        if load_token is not None:
            _load_context.reset(load_token)
        _quiet_collisions.reset(quiet_token)
        _freshness_cache.reset(freshness_token)
```

- [ ] **Step 4: Add `quiet_collisions()` and the collision gate in `pyjinhx/registry.py`**

Replace the import block at registry.py:9-12 with:

```python
import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pyjinhx.session import (
    _instances,
    _quiet_collisions,
    get_dev_strict,
    get_instances,
    get_quiet_collisions,
)
```

Add the context manager immediately after `InstanceKeyCollisionError` (registry.py:60-66) and before `register_instance`:

```python
@contextmanager
def quiet_collisions(keys: Iterable[str]) -> Iterator[None]:
    """Mark composite keys whose collision is expected for the duration of the block.

    A write to one of these keys still overwrites — last-write-wins is
    unchanged — but skips the warning and the dev-strict raise. Nested blocks
    union: an inner block adds to the outer one's set, and the exit restores the
    outer one exactly, including when the body raises. Used outside an active
    request_scope() this binds and restores a set nothing reads, which is a
    no-op rather than an error: the mechanism is advisory noise-suppression.

    Args:
        keys: Composite keys, as make_key() builds them.

    Yields:
        None; the block body runs with those keys quieted.
    """
    token = _quiet_collisions.set(get_quiet_collisions() | frozenset(keys))
    try:
        yield
    finally:
        # Reset by token, never by assigning the old value back: a worker's
        # copied context and a nested block both have to hand back exactly what
        # they were handed, and only the token knows what that was.
        _quiet_collisions.reset(token)
```

Then gate the collision branch. Replace registry.py:95-105:

```python
    if key in instances and key not in get_quiet_collisions():
        # The one production caller fires once per rendered component, so a
        # second write to one key in one request means two components claimed
        # the same id — usually a hard-coded `id` default on a class rendered
        # more than once. Unless a caller said otherwise: a key inside an
        # active quiet_collisions() block is one this request already knows two
        # builds will claim (#1022 — a region rendered both as its own fan-out
        # candidate and as a nested descendant of a sibling candidate's tree),
        # so it overwrites in silence.
        if get_dev_strict():
            raise InstanceKeyCollisionError(
                f"Key {key!r} is already registered; two instances share one id."
            )
        logger.warning("Key %r is already registered; overwriting.", key)
    instances[key] = entry
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/pyjinhx/test_instance_registry.py::test_a_quieted_key_collides_silently_and_still_last_write_wins -v`
Expected: PASS

- [ ] **Step 6: Write the boundary tests — unquieted keys, dev-strict, and life after the block**

Append to `tests/pyjinhx/test_instance_registry.py`:

```python
def test_a_key_outside_the_quiet_set_still_warns_while_another_is_quieted(caplog):
    """Quieting is per key, not a mode: the block does not hush the whole request."""
    with request_scope(), caplog.at_level(logging.WARNING, logger="pyjinhx"):
        register_instance("Widget", "w1", Widget("first"))
        register_instance("Widget", "w2", Widget("first"))
        with quiet_collisions([make_key("Widget", "w1")]):
            register_instance("Widget", "w1", Widget("second"))
            register_instance("Widget", "w2", Widget("second"))
    assert len(caplog.records) == 1
    assert "Widget_w2" in caplog.records[0].getMessage()


def test_strict_mode_skips_the_raise_for_a_quieted_key_only(strict_dev):
    """Dev-strict's false positive on the benign shape goes; the real one stays."""
    second = Widget("second")
    with request_scope():
        register_instance("Widget", "w1", Widget("first"))
        register_instance("Widget", "w2", Widget("first"))
        with quiet_collisions([make_key("Widget", "w1")]):
            register_instance("Widget", "w1", second)
            assert resolve("Widget", "w1") is second
            with pytest.raises(InstanceKeyCollisionError, match="Widget_w2"):
                register_instance("Widget", "w2", Widget("second"))


def test_the_same_key_collides_loudly_again_after_the_block_exits(caplog):
    """The suppression is scoped to the block, not sticky for the request."""
    with request_scope(), caplog.at_level(logging.WARNING, logger="pyjinhx"):
        register_instance("Widget", "w1", Widget("first"))
        with quiet_collisions([make_key("Widget", "w1")]):
            register_instance("Widget", "w1", Widget("second"))
        assert caplog.records == []
        register_instance("Widget", "w1", Widget("third"))
    assert len(caplog.records) == 1
    assert "Widget_w1" in caplog.records[0].getMessage()
```

- [ ] **Step 7: Run the boundary tests**

Run: `uv run pytest tests/pyjinhx/test_instance_registry.py -v -k "quiet or strict_mode_skips or collides_loudly"`
Expected: PASS (4 tests). These are guard tests over the Non-goals — a per-key check and a token-scoped block already satisfy them. A failure here means the gate is too broad (hushing the whole request) or the block leaks; fix the implementation, not the test.

- [ ] **Step 8: Write the lifetime tests — scope isolation, nesting, exceptions, out-of-scope**

Append to `tests/pyjinhx/test_instance_registry.py`:

```python
def test_the_quiet_set_is_bound_per_scope_and_restored_on_exit():
    """An inner scope starts empty and hands the outer one its own set back."""
    assert get_quiet_collisions() == frozenset()
    with request_scope():
        assert get_quiet_collisions() == frozenset()
        with quiet_collisions([make_key("Widget", "w1")]):
            assert get_quiet_collisions() == frozenset({"Widget_w1"})
            with request_scope():
                assert get_quiet_collisions() == frozenset()
                with quiet_collisions([make_key("Widget", "inner")]):
                    assert get_quiet_collisions() == frozenset({"Widget_inner"})
            assert get_quiet_collisions() == frozenset({"Widget_w1"})
    assert get_quiet_collisions() == frozenset()
    with request_scope():
        assert get_quiet_collisions() == frozenset()


def test_nested_quiet_blocks_union_and_restore_the_outer_set():
    """Composition, so a future second caller cannot strand the first one's set."""
    with request_scope(), quiet_collisions([make_key("Widget", "a")]):
        with quiet_collisions([make_key("Widget", "b")]):
            assert get_quiet_collisions() == frozenset({"Widget_a", "Widget_b"})
        assert get_quiet_collisions() == frozenset({"Widget_a"})


def test_quiet_collisions_restores_the_previous_set_when_the_body_raises():
    """The build pass lets a loader's exception travel; the set must not travel with it."""
    with request_scope():
        with pytest.raises(RuntimeError, match="boom"):
            with quiet_collisions([make_key("Widget", "w1")]):
                assert get_quiet_collisions() == frozenset({"Widget_w1"})
                raise RuntimeError("boom")
        assert get_quiet_collisions() == frozenset()


def test_quiet_collisions_outside_request_scope_raises_nothing(caplog):
    """Advisory, not load-bearing: no scope means no new failure mode."""
    assert _instances.get() is None
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        with quiet_collisions([make_key("Widget", "w1")]):
            register_instance("Widget", "w1", Widget("orphan"))
    # The out-of-scope drop happens before any quiet-set check, so its warning
    # is untouched by the block.
    assert len(caplog.records) == 1
    assert "outside request_scope()" in caplog.records[0].getMessage()
    assert get_quiet_collisions() == frozenset()
```

- [ ] **Step 9: Run the lifetime tests**

Run: `uv run pytest tests/pyjinhx/test_instance_registry.py -v -k "bound_per_scope or nested_quiet or restores_the_previous or outside_request_scope_raises_nothing"`
Expected: PASS (4 tests). If `test_the_quiet_set_is_bound_per_scope_and_restored_on_exit` fails, `request_scope()` is missing the set/reset pair from Step 3.

- [ ] **Step 10: Amend the invariant-4 census**

In `docs/superpowers/rebuild/architecture-overview.md`, replace line 167's census sentence so the new ContextVar is enumerated (the rest of the paragraph is unchanged):

```markdown
**Discovery and `{#def#}` are the only writers at import time; everything per-request is ContextVar.** The full mutable-state census (invariant 4): class registry + descriptors (built-then-swap, import/registration time), instance registry + RenderSession + dirtied keys + LoadCache request store + LoadCache reverse index + template-freshness cache + expected-collision key set (ContextVar, reset by `request_scope`). Nothing else. A mechanism needing mutable state not in this census amends this census first.
```

- [ ] **Step 11: Run the whole per-module registry and session suites**

Run: `uv run pytest tests/pyjinhx/test_instance_registry.py tests/pyjinhx/test_session.py tests/pyjinhx/test_import_graph.py -v`
Expected: PASS, with no edit to `tests/pyjinhx/test_import_graph.py`.

- [ ] **Step 12: Commit**

```bash
git add pyjinhx/session.py pyjinhx/registry.py docs/superpowers/rebuild/architecture-overview.md tests/pyjinhx/test_instance_registry.py
git commit -m "feat: request-scoped quiet set for expected registry collisions (#1024)"
```

---

### Task 2: Wire the quiet set through the fan-out build pass

**Files:**
- Modify: `pyjinhx/reactive/fanout.py:520-534` (`_build_one`), `pyjinhx/reactive/fanout.py:583-593` (`_build_pass`)
- Modify: `scripts/bench_reactive_fanout.py:319-329`
- Test: `tests/pyjinhx/reactive/test_reactive_fanout.py`

**Interfaces:**
- Consumes: `registry.quiet_collisions(keys)` and `registry.make_key(type_name, instance_id)` from Task 1.
- Produces: `_build_one(item: _WorkItem, session: RenderSession, pass_keys: frozenset[str]) -> _BuildResult` — a third positional parameter. `_build_pass(items: list[_WorkItem], session: RenderSession) -> dict[int, _BuildResult]` keeps its signature.

- [ ] **Step 1: Add the test fixtures for a parent that nests a child by `ChildRef` tag**

In `tests/pyjinhx/reactive/test_reactive_fanout.py`, add `import logging` to the stdlib import block (currently `dataclasses, pathlib, re, sys, threading, time`), add `from pyjinhx import dev` beside the existing `from pyjinhx import discovery, registry`, and add the stamping hook to the `root_attrs` import:

```python
from pyjinhx.reactive.root_attrs import record_nested_react_keys, stamp_reactive_root_attrs
```

Add these module-level definitions after the `LoudWidget` class (test file line 79):

```python
CHILD_REGISTERED = threading.Event()
"""Set once NestedChildWidget has rendered and registered under its own id.

NestingParentWidget.load() waits on it so the #1022 ordering under test is the
one the issue reports: the child's *own* top-level build registers first, and
the parent's nested re-render of the same region is the second, colliding
write. Without the gate the two pool workers race and the test would assert on
whichever finished first.
"""


class NestedChildWidget(ReactiveComponent, react=("todos",)):
    """A reactive child that NestingParentWidget's template mounts by tag."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "NestedChildWidget":
        LOAD_CALLS.append(f"child:{pjx_key}")
        return cls(pjx_key=pjx_key)


class NestingParentWidget(ReactiveComponent, react=("todos",)):
    """A reactive parent whose template nests NestedChildWidget under a fixed id."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "NestingParentWidget":
        LOAD_CALLS.append(f"parent:{pjx_key}")
        CHILD_REGISTERED.wait(timeout=5)
        return cls(pjx_key=pjx_key)


def _child_registered(component, level, session) -> None:
    """An on_rendered subscriber that releases NestingParentWidget.load()."""
    if isinstance(component, NestedChildWidget):
        CHILD_REGISTERED.set()


def wired_session() -> RenderSession:
    """A session wired the way integrations/fastapi.py:208-210 wires a request's.

    The stamp hook is what writes each rendered root's ``data-pjx-id``, which is
    what `_drop_nested`'s containment check reads; the registry writer is what
    makes the double registration happen at all. The releaser goes last, so it
    only fires once the write it is reporting has landed.
    """
    session = RenderSession()
    session.on_rendered.append(stamp_reactive_root_attrs)
    session.on_rendered.append(registry.register_rendered_instance)
    session.on_rendered.append(_child_registered)
    return session


@pytest.fixture
def strict_dev():
    """Reactive-dev strict mode on for one test, off again afterwards.

    Process-wide, not request-scoped, so leaving it on would leak into every
    test that runs after this one.
    """
    dev.enable_reactive_dev(strict=True)
    yield
    dev.disable_reactive_dev()
```

In the autouse `_clean_registries` fixture (test file lines 125-175), clear the event, write the two templates, register the classes and point their descriptors at the tmp_path files. Add after the `loud_path` lines:

```python
    CHILD_REGISTERED.clear()
    child_path = tmp_path / "nested_child_widget.pjx"
    child_path.write_text("<div>child {{ pjx_key }}</div>")
    parent_path = tmp_path / "nesting_parent_widget.pjx"
    parent_path.write_text(
        '<div>parent <NestedChildWidget pjx_key="k1" id="child-1" /></div>'
    )
```

change the `build_registry` call to:

```python
    discovery.build_registry(
        tmp_path,
        [
            FanoutWidget,
            QuietWidget,
            PlainWidget,
            SpyWidget,
            LoudWidget,
            OwnedWidget,
            NestedChildWidget,
            NestingParentWidget,
        ],
    )
```

and add these two descriptor rewrites beside the existing ones, above the `yield`:

```python
    NestedChildWidget.__pjx_descriptor__ = dataclasses.replace(
        NestedChildWidget.__pjx_descriptor__, template_path=child_path
    )
    NestingParentWidget.__pjx_descriptor__ = dataclasses.replace(
        NestingParentWidget.__pjx_descriptor__, template_path=parent_path
    )
```

- [ ] **Step 2: Write the failing test — the nested double-registration is silent**

Append to `tests/pyjinhx/reactive/test_reactive_fanout.py`:

```python
def nesting_manifest() -> list[dict]:
    """The #1022 manifest: the nested child first, then its containing parent.

    Child first is deliberate. The child's own dedicated build registers
    `NestedChildWidget_child-1`; the parent's build then re-renders the same
    region as a nested descendant and writes that key a second time. That second
    write is the one this subtask quiets.
    """
    return [
        entry("nested_child_widget", "child-1", load="k1"),
        entry("nesting_parent_widget", "parent-1", load="k1"),
    ]


def test_a_nested_child_that_is_also_its_own_candidate_registers_silently(caplog):
    session = wired_session()
    with (
        request_scope(session=session),
        caplog.at_level(logging.WARNING, logger="pyjinhx"),
    ):
        walk_manifest(nesting_manifest(), {"todos"})

    assert [record.getMessage() for record in caplog.records] == []
    # Both builds really ran — the quieting is about the noise, not about
    # skipping the redundant work (an explicit Non-goal).
    assert "child:k1" in LOAD_CALLS
    assert "parent:k1" in LOAD_CALLS
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_fanout.py::test_a_nested_child_that_is_also_its_own_candidate_registers_silently -v`
Expected: FAIL — one captured WARNING record, `"Key 'NestedChildWidget_child-1' is already registered; overwriting."`

- [ ] **Step 4: Compute the pass's key set and open the quiet block per item**

In `pyjinhx/reactive/fanout.py`, replace `_build_one` (lines 520-534) with:

```python
def _build_one(
    item: _WorkItem, session: RenderSession, pass_keys: frozenset[str]
) -> _BuildResult:
    """One work item's load and render, with its own absence proof caught.

    The LookupError is caught per item rather than per pass so one region the
    server no longer knows about cannot decide any sibling's outcome. Every
    other exception is left to travel, exactly as it did before the build ran
    off-thread.

    ``pass_keys`` carries every filtered item's composite key; this item's own is
    removed before the quiet block opens. What is left is "ids this request's
    client-reported manifest already lists as separately-mounted top-level
    regions", so a component reached as a nested descendant of this build's tree
    whose id is one of them is #1022's benign double-render, not an authoring
    mistake, and its second registry write says nothing worth logging. A
    collision on this item's *own* key is the opposite claim — something else
    took the exact key this build is about to write — and stays loud.

    The block is entered here, inside the worker, so on the threaded branch it
    lives entirely within that worker's copied context and cannot disturb a
    sibling's or the submitting thread's view.
    """
    own_key = registry.make_key(item.component_class.__name__, item.instance_id)
    try:
        with registry.quiet_collisions(pass_keys - {own_key}):
            instance, level = _build_dirty(
                item.component_class, item.instance_id, item.load, session
            )
    except LookupError:
        return _BuildResult(instance=None, level=None, missing=True)
    return _BuildResult(instance=instance, level=level, missing=False)
```

Then in `_build_pass`, replace the body after the docstring (lines 583-593) with:

```python
    pending = [item for item in items if not item.clean]
    if not pending:
        return {}
    # Computed once, from the whole filtered list, before anything is built:
    # what a build may benignly re-register is decided by the client's manifest,
    # never by something a render discovers about itself midway. Clean items are
    # included — a clean sibling is still a separately-mounted region, and its id
    # turning up inside a dirty build's tree is the same benign shape.
    pass_keys = frozenset(
        registry.make_key(item.component_class.__name__, item.instance_id)
        for item in items
    )
    if all(is_too_cheap_to_thread(item.component_class) for item in pending):
        return {item.index: _build_one(item, session, pass_keys) for item in pending}
    with ThreadPoolExecutor(max_workers=min(8, len(pending))) as pool:
        futures = {
            item.index: pool.submit(
                copy_context().run, _build_one, item, session, pass_keys
            )
            for item in pending
        }
        return {index: future.result() for index, future in futures.items()}
```

Add one sentence to `_build_pass`'s docstring, immediately after the "One copy per item..." paragraph (before the "A pass whose every item is a class already measured..." paragraph):

```python
    Each item's build runs with every *other* item's composite key quieted, so
    the registry stops reporting #1022's structural double-registration — one
    region built both as its own candidate and as a nested descendant of a
    sibling's tree — as an id clash. See ``_build_one``.
```

- [ ] **Step 5: Update the bench script's direct `_build_one` caller**

`scripts/bench_reactive_fanout.py` calls `_build_one` by hand for its sequential leg and is executed by `tests/test_bench_scripts_smoke.py`. Replace lines 324-330:

```python
        with request_scope():
            session, items = _build_items(candidates_n, template_dir)
            # The same set _build_pass computes, so the sequential leg prices the
            # identical work — including the quiet block each build opens.
            pass_keys = frozenset(
                registry.make_key(item.component_class.__name__, item.instance_id)
                for item in items
            )
            t0 = time.perf_counter()
            for item in items:
                _build_one(item, session, pass_keys)
            sequential = time.perf_counter() - t0
        return concurrent, sequential
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_fanout.py::test_a_nested_child_that_is_also_its_own_candidate_registers_silently -v`
Expected: PASS

- [ ] **Step 7: Write the dev-strict, output-parity and inline-branch tests**

Append to `tests/pyjinhx/reactive/test_reactive_fanout.py`:

```python
def test_the_nested_double_registration_does_not_crash_dev_strict(strict_dev):
    """Today's false positive: dev-strict turns the benign shape into a 500."""
    session = wired_session()
    with request_scope(session=session):
        candidates = walk_manifest(nesting_manifest(), {"todos"})

    assert [candidate.instance_id for candidate in candidates] == ["parent-1"]


def test_the_nesting_dedup_output_is_unchanged_by_the_quieting():
    """Non-goal guard: which swap ships is still _drop_nested's call, unchanged."""
    session = wired_session()
    with request_scope(session=session):
        candidates = walk_manifest(nesting_manifest(), {"todos"})
        body = oob_swaps(candidates)

    assert [(c.instance_id, c.status) for c in candidates] == [("parent-1", "dirty")]
    swaps = re.findall(r'hx-swap-oob="([^:]+):\[data-pjx-id=\'([^\']+)\'', body)
    assert swaps == [("outerHTML", "parent-1")]


def test_two_unrelated_candidates_sharing_one_id_still_warn(caplog):
    """The authoring bug is not masked: neither region is nested in the other."""
    session = wired_session()
    manifest = [
        entry("fanout_widget", "shared", load="todo-1"),
        entry("fanout_widget", "shared", load="todo-2"),
    ]
    with (
        request_scope(session=session),
        caplog.at_level(logging.WARNING, logger="pyjinhx"),
    ):
        walk_manifest(manifest, {"todos"})

    messages = [record.getMessage() for record in caplog.records]
    assert [m for m in messages if "FanoutWidget_shared" in m and "overwriting" in m]


def test_two_unrelated_candidates_sharing_one_id_still_raise_under_strict(strict_dev):
    """Same shape, dev-strict: the raise still travels out of the build pass."""
    session = wired_session()
    manifest = [
        entry("fanout_widget", "shared", load="todo-1"),
        entry("fanout_widget", "shared", load="todo-2"),
    ]
    with request_scope(session=session):
        with pytest.raises(InstanceKeyCollisionError, match="FanoutWidget_shared"):
            walk_manifest(manifest, {"todos"})


def test_the_quieting_holds_on_the_inline_build_branch(caplog):
    """The all-cheap branch runs on the caller's own ContextVars, not a copy."""
    note_load_cost(NestedChildWidget, 0.0)
    note_load_cost(NestingParentWidget, 0.0)

    def no_pool(*args, **kwargs):
        raise AssertionError("the too-cheap path must not build a ThreadPoolExecutor")

    session = wired_session()
    with (
        request_scope(session=session),
        pytest.MonkeyPatch.context() as patch,
        caplog.at_level(logging.WARNING, logger="pyjinhx"),
    ):
        patch.setattr(fanout, "ThreadPoolExecutor", no_pool)
        candidates = walk_manifest(nesting_manifest(), {"todos"})

    assert [record.getMessage() for record in caplog.records] == []
    assert [candidate.instance_id for candidate in candidates] == ["parent-1"]
    # And the block left nothing behind on the caller's own context.
    assert get_quiet_collisions() == frozenset()
```

Add the two names these tests need to the existing imports: `InstanceKeyCollisionError` to the `pyjinhx.registry` surface (import it as `from pyjinhx.registry import InstanceKeyCollisionError`, leaving the existing `from pyjinhx import discovery, registry` alone) and `get_quiet_collisions` to the `pyjinhx.session` import block at test file lines 29-35:

```python
from pyjinhx.session import (
    RenderSession,
    current_session,
    get_cache_store,
    get_load_context,
    get_quiet_collisions,
    request_scope,
)
```

- [ ] **Step 8: Run the new fan-out tests**

Run: `uv run pytest tests/pyjinhx/reactive/test_reactive_fanout.py -v -k "nested_double_registration or nesting_dedup_output or unrelated_candidates or quieting_holds or registers_silently"`
Expected: PASS (6 tests).

- [ ] **Step 9: Run the whole fan-out module and the import-graph guard**

Run: `uv run pytest tests/pyjinhx/reactive/ tests/pyjinhx/test_import_graph.py -v`
Expected: PASS. `test_module_never_registers_instances` must still pass — the new fan-out code calls `registry.quiet_collisions(` and `registry.make_key(`, never `register_instance(`.

- [ ] **Step 10: Commit**

```bash
git add pyjinhx/reactive/fanout.py scripts/bench_reactive_fanout.py tests/pyjinhx/reactive/test_reactive_fanout.py
git commit -m "fix: quiet the fan-out pass's expected registry collisions (#1024)"
```

---

### Task 3: End-to-end proof through the production `on_rendered` wiring

**Files:**
- Create: `tests/templates/cycle_shell.pjx`, `tests/templates/cycle_nested.pjx`
- Test: `tests/pyjinhx/integrations/test_reactive_request_cycle.py`

**Interfaces:**
- Consumes: the Task 1 gate and the Task 2 wiring, reached only through `apply_setup`'s middleware (`pyjinhx/integrations/fastapi.py:208-210`).
- Produces: nothing further tasks depend on.

- [ ] **Step 1: Create the two templates**

`tests/templates/cycle_nested.pjx`:

```html
<div>nested {{ pjx_key }}</div>
```

`tests/templates/cycle_shell.pjx`:

```html
<div class="shell">shell <CycleNested pjx_key="card-1" id="n" /></div>
```

- [ ] **Step 2: Write the failing end-to-end test**

In `tests/pyjinhx/integrations/test_reactive_request_cycle.py`, add the load-cost import beside the existing reactive imports:

```python
from pyjinhx.reactive.load_cost import note_load_cost
```

Add the two component classes after `CycleBadge` (file line 81):

```python
class CycleNested(ReactiveComponent, react=(Keys.CYCLE,)):
    """A region CycleShell's template mounts by tag under the id ``n``."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "CycleNested":
        LOAD_CALLS.append(f"nested:{pjx_key}")
        return cls(pjx_key=pjx_key)


class CycleShell(ReactiveComponent, react=(Keys.CYCLE,)):
    """A region whose own render nests CycleNested — the #1022 shape."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "CycleShell":
        LOAD_CALLS.append(f"shell:{pjx_key}")
        return cls(pjx_key=pjx_key)
```

Register them in the autouse `_publish_registry` fixture: change the `build_registry` call to

```python
    discovery.build_registry(
        template_dir, [CycleCard, CycleBadge, CycleNested, CycleShell]
    )
```

and add the two descriptor rewrites above the fixture's `yield`:

```python
    CycleNested.__pjx_descriptor__ = dataclasses.replace(
        CycleNested.__pjx_descriptor__, template_path=template_dir / "cycle_nested.pjx"
    )
    CycleShell.__pjx_descriptor__ = dataclasses.replace(
        CycleShell.__pjx_descriptor__, template_path=template_dir / "cycle_shell.pjx"
    )
```

Then append the test at the end of the file:

```python
def test_a_nested_child_candidate_swaps_without_a_registry_collision_warning(caplog):
    """#1022 through the real middleware: no warning, same swaps, still 200.

    Both classes are pre-measured as too cheap to thread, so `_build_pass` runs
    them inline in manifest order: the nested child's own build registers
    `CycleNested_n` first, and the shell's build then re-renders that same region
    as a descendant and writes the key a second time. That second write is what
    used to log "already registered; overwriting" on every such request.
    """
    app = make_app()
    STORE["card-1"] = 0
    note_load_cost(CycleNested, 0.0)
    note_load_cost(CycleShell, 0.0)

    @app.post("/bump")
    def bump(request: Request):
        Counter().bump("card-1")
        invalidate(get_dirtied())

    with caplog.at_level(logging.WARNING, logger="pyjinhx"), TestClient(app) as client:
        response = client.post(
            "/bump",
            headers={
                "X-PJX-Mounted": json.dumps(
                    [
                        {
                            "type": "cycle_nested",
                            "id": "n",
                            "load": "card-1",
                            "hash": "stale",
                        },
                        {
                            "type": "cycle_shell",
                            "id": "s",
                            "load": "card-1",
                            "hash": "stale",
                        },
                    ]
                ),
                "X-PJX-Assets": "[]",
            },
        )

    body = response.text
    assert response.status_code == 200
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='s']\"" in body
    # The nested region ships inside the shell's swap, never as its own:
    # _drop_nested's output filtering is untouched by this subtask.
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='n']\"" not in body
    assert "nested card-1" in body
    collisions = [
        record.getMessage()
        for record in caplog.records
        if "already registered" in record.getMessage()
    ]
    assert collisions == []
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/pyjinhx/integrations/test_reactive_request_cycle.py::test_a_nested_child_candidate_swaps_without_a_registry_collision_warning -v`
Expected: PASS on a branch that already carries Tasks 1-2. To see the RED this test pins, run it once with the gate reverted:

```bash
git stash push pyjinhx/registry.py
uv run pytest tests/pyjinhx/integrations/test_reactive_request_cycle.py::test_a_nested_child_candidate_swaps_without_a_registry_collision_warning -v
git stash pop
```

Expected under the stash: FAIL on `assert collisions == []` with `"Key 'CycleNested_n' is already registered; overwriting."`. If it fails for any other reason — a 500, a missing swap, a `TemplateNotFound` — the fixture wiring is wrong, not the gate.

- [ ] **Step 4: Run the whole integrations tier**

Run: `uv run pytest tests/pyjinhx/integrations/ -v`
Expected: PASS. The two new classes are additive; no existing test in the file names them.

- [ ] **Step 5: Commit**

```bash
git add tests/templates/cycle_shell.pjx tests/templates/cycle_nested.pjx tests/pyjinhx/integrations/test_reactive_request_cycle.py
git commit -m "test: end-to-end proof that a nested candidate no longer warns (#1024)"
```

---

### Task 4: The stale docstring, and full verification

**Files:**
- Modify: `pyjinhx/registry.py:111-115`

**Interfaces:**
- Consumes: everything above. Produces: nothing.

- [ ] **Step 1: Correct `register_rendered_instance`'s stale docstring sentence**

The current text claims the hook is "subscribed by no production code", which `pyjinhx/integrations/fastapi.py:210` contradicts. Replace the docstring's first paragraph pair (registry.py:111-115) with:

```python
    """Register a just-rendered component's level under its composite key.

    Shaped for ``RenderSession.on_rendered`` and subscribed onto every request's
    session by ``integrations/fastapi.py``'s middleware; a hand-built session
    that never attaches it registers nothing.
```

Leave the `Args:` block and the rest of the function untouched — one sentence, no scope creep.

- [ ] **Step 2: Format**

Run: `ruff format .`
Expected: files reformatted or "N files left unchanged"; re-run the tests below after any reformat.

- [ ] **Step 3: Lint**

Run: `ruff check .`
Expected: "All checks passed!"

- [ ] **Step 4: Type-check**

Run: `uvx "basedpyright==1.39.9" pyjinhx/`
Expected: 0 errors. Watch for `_build_one`'s new `pass_keys: frozenset[str]` parameter and `get_quiet_collisions() -> frozenset[str]` agreeing at every call site — `pass_keys - {own_key}` is `frozenset[str]`, and `quiet_collisions` takes `Iterable[str]`.

- [ ] **Step 5: Install the browser tier's dependency**

Run: `uv run playwright install --with-deps chromium`
Expected: chromium installed (or already up to date). Own invocation — do not chain.

- [ ] **Step 6: Run the library test tier**

Run: `uv run pytest tests/pyjinhx/`
Expected: PASS, no new failures, `tests/pyjinhx/test_import_graph.py` untouched and green.

- [ ] **Step 7: Run the full test suite**

Run: `uv run pytest tests/`
Expected: PASS, including `tests/test_bench_scripts_smoke.py`, which executes `scripts/bench_reactive_fanout.py` and therefore the updated `_build_one` call.

- [ ] **Step 8: Commit**

```bash
git add pyjinhx/registry.py
git commit -m "docs: register_rendered_instance is wired by the FastAPI middleware (#1024)"
```

---

## Self-Review

Run against the spec, after the plan was written:

**1. Spec coverage.** Scope item 1 (session ContextVar + getter + `request_scope` set/reset) — Task 1 Step 3. Item 2 (`quiet_collisions`) — Task 1 Step 4. Item 3 (collision-branch gate) — Task 1 Step 4. Item 4 (`_build_one`/`_build_pass` wiring) — Task 2 Step 4. Item 5 ("eight pieces" → nine) — Task 1 Step 3. Item 6 (architecture-overview.md:167 census) — Task 1 Step 10. Opportunistic docstring fix — Task 4 Step 1. Observable behavior bullets map to registry tests 1-7 (Task 1 Steps 1/6/8) and fan-out tests 8-12 (Task 2 Steps 2/7); the "both `_build_pass` branches" bullet is split between the threaded default (Task 2 Steps 2 and 7) and the explicit inline branch test (Task 2 Step 7, `test_the_quieting_holds_on_the_inline_build_branch`). Error paths: out-of-scope no-op and nesting composition and exception restore all in Task 1 Step 8; "no new exception type" is satisfied by construction (no new class in any code block). Layering: no `test_import_graph.py` edit anywhere; asserted green in Task 1 Step 11 and Task 2 Step 9. Test 13 — Task 3. One extra file the spec did not enumerate, `scripts/bench_reactive_fanout.py`, is in Task 2 Step 5: it calls `_build_one` directly and `tests/test_bench_scripts_smoke.py` runs it, so leaving it out would break tier 3.

**2. Placeholder scan.** No "TBD", no "similar to Task N", no "add appropriate error handling"; every code step carries the literal code. The one non-literal instruction is Task 4 Step 1's "leave the `Args:` block untouched", which describes what *not* to edit rather than deferring work.

**3. Type consistency.** `_quiet_collisions: ContextVar[frozenset[str] | None]` / `get_quiet_collisions() -> frozenset[str]` / `quiet_collisions(keys: Iterable[str]) -> Iterator[None]` / `_build_one(item, session, pass_keys: frozenset[str])` / `pass_keys = frozenset(...)` in both `_build_pass` and the bench script. Set arithmetic stays inside `frozenset` (`get_quiet_collisions() | frozenset(keys)`, `pass_keys - {own_key}`). Test assertions compare against `frozenset({...})`, matching the getter's return type. `registry.make_key(type_name, instance_id)` is used with the class `__name__` (PascalCase) on both the fan-out and bench sides, matching what `register_rendered_instance` writes under.

**Carried caveat:** the exploration findings handed to this stage were truncated mid-sentence inside the test-placement rule ("Placemen..."), and the spec summary was truncated too. Tier assignment here was made by reading the tier docstrings in the real files (`tests/pyjinhx/test_instance_registry.py`, `tests/pyjinhx/reactive/test_reactive_fanout.py` — hand-entered scopes; `tests/pyjinhx/integrations/test_reactive_request_cycle.py` — "nothing here enters `request_scope()` by hand") rather than from the truncated rule text, and it matches the spec's own tier assignment for all 13 tests.
