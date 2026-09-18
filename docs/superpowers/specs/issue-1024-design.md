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
