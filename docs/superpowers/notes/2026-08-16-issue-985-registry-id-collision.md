# Decision: raise condition for `register_instance` id collisions (#985)

Issue #985 (subtask of #977). Decision and write-up only — no code diff. Sibling #986 implements.

## Decision

**(b) — debug-gated.** `register_instance` raises on a same-request key collision **only when the existing reactive dev strict flag is on**; otherwise it keeps logging the warning it logs today and overwrites, exactly as `pyjinhx/registry.py:81-82` does now.

Concretely, the collision branch #986 will write behaves as:

- `dev` strict on -> raise.
- `dev` enabled but not strict, or `dev` off entirely -> `logger.warning("Key %r is already registered; overwriting.", key)` and overwrite (today's behaviour, unchanged).

### Why (b) and not (a) always-raise

`pyjinhx/dev.py:23-55` is the only place in the codebase that already implements "raise if strict, else warn": `_DevConfig(enabled, strict)`, set by `enable_reactive_dev(strict=...)`, read by `_report()`, which raises `RuntimeError` when `_dev_config.strict` and logs a warning otherwise. The `enabled` half of that switch is reachable from configuration a project already has — `PjxSettings.reactive_dev` / the `PJX_REACTIVE_DEV` env var, applied through `config.configure_pyjinhx` -> `_apply_reactive_dev`. The `strict` half is not: `_apply_reactive_dev` (`pyjinhx/config.py:121-137`) only ever calls `dev.enable_reactive_dev()` with no `strict` argument, so it defaults to `strict=False` — there is no config field or env var today that reaches `strict=True`, only a direct `enable_reactive_dev(strict=True)` call in code. Routing this collision through the same `_DevConfig.strict` switch means a project has exactly one flag controlling how loudly pyjinhx surfaces developer-error findings, instead of one flag plus one hardcoded always-raise site — but wiring `strict` up to configuration (a `PjxSettings` field and/or env var) is not yet built and is not part of this decision's scope.

Always-raise was rejected for a second, concrete reason: today's behaviour is warn-and-overwrite, and the registry cannot prove that every same-key write is a bug (see "Open question for #986"). Turning an unproven signal into an unconditional exception on the render path risks breaking working applications on a false positive. Debug-gating gives the loud failure to the developer who asked for it and leaves production on the current, non-breaking path.

### Exception type

**`InstanceKeyCollisionError`**, a new exception defined in `pyjinhx/registry.py` alongside the function that raises it.

Not `LookupError`: ADR 0009 (`docs/superpowers/rebuild/adr/0009-minimal-instance-registry.md`, "Miss representation") reserves `LookupError` for `resolve()` failing to find a key. A collision is the opposite failure — the key is present *twice* — and reusing `LookupError` would make `except LookupError` around a resolve/register pair catch two unrelated conditions.

Not bare `RuntimeError` (what `dev._report()` raises): a caller who wants to tolerate collisions in strict mode should be able to name this case without also swallowing every other `RuntimeError` the render path can produce. `InstanceKeyCollisionError` should subclass `RuntimeError` so that code already catching `RuntimeError` around strict-mode dev findings keeps working.

### Mechanism: how `#986` reaches the strict flag without breaking layering

`pyjinhx/registry.py`'s docstring places it below the spine — read and written only by the Load path — and `tests/pyjinhx/test_import_graph.py`'s `ALLOWED_INTERNAL_IMPORTS["registry"]` is `frozenset({"pyjinhx.session", "pyjinhx.segments"})`, checked with `ast.walk()` over the whole file, which does not distinguish module-scope from function-local imports. So `register_instance` must **not** grow *any* `from pyjinhx import dev` — not a top-level one, and not a function-local one either; either form fails `test_module_imports_only_declared_internal_modules` for the `"registry"` module. `pyjinhx/dev.py`'s own docstring says, unqualified, "nothing below it imports this module back" — it carries none of `config`'s narrow carve-out for function-local reads (that carve-out is `config`'s own, pinned by three named tests, and covers *config* being read from below — not *dev*).

The pattern this decision originally proposed copying, `config._apply_reactive_dev` (`pyjinhx/config.py:126-142`), is not a usable precedent for `registry`: it is `config` (declared above the spine) importing `dev` (also declared above the spine — `ALLOWED_INTERNAL_IMPORTS["config"]` explicitly lists `"pyjinhx.dev"` as a lateral, already-granted edge), not a spine module reaching upward.

The correct mechanism inverts the direction. `dev.py` already imports `pyjinhx.session` (`from pyjinhx.session import get_cache_reverse, get_dirtied` — a declared edge), and `registry.py` already imports `pyjinhx.session` too. So `dev.enable_reactive_dev()`/`disable_reactive_dev()` should push the strict flag *down* into a small piece of state `session.py` owns (e.g. a module-level flag with a getter/setter, the same shape `_instances` already has there), and `register_instance` should read it back through the `session` import it already has — the same value `dev._report()` already gates on (`_dev_config.strict`), just reached from below instead of above. This adds **zero new edges** to `ALLOWED_INTERNAL_IMPORTS`, so #986 needs no change to `tests/pyjinhx/test_import_graph.py` for this wiring. #986 must implement the collision check this way, not via any `dev` import inside `registry.py`. The flag itself should be a plain module-level value, process-wide like `dev._dev_config` already is (set once when `enable_reactive_dev`/`disable_reactive_dev` runs) — **not** a `ContextVar`, so it does not join `architecture-overview.md`'s invariant-4 per-request mutable-state census and #986 does not need to amend that census for it.

## Reaffirmed boundaries (fixed by parent #977 — not reopened here)

1. **No class-definition-time check for literal `id` defaults.** `FixedId`-style singletons that declare a literal `id` default at class-definition time get no new validation. `tests/pyjinhx/test_component.py:461-467` (`test_id_default_and_metadata_may_be_overridden`) stays green not by exemption but by construction: it declares a class with an overridden `id` default and instantiates it, and the decision here only fires inside `register_instance`, on the *second* write to one key within one request scope. A single `FixedId()` instance per request writes its key once, so no collision branch is ever entered — the test never reaches the changed code.

2. **Non-unique `default_factory` values are out of scope.** An `id` field whose factory returns a constant (e.g. `default_factory=lambda: "static-id"`) will produce colliding keys, and this decision does nothing to detect that at the factory. It is only visible, like any other duplicate, at the second `register_instance` call — which is what the debug-gated raise reports. No separate factory-level guard is being designed.

## Open question left to #986

`register_instance`'s only production caller is `register_rendered_instance` (`pyjinhx/registry.py:86-102`), subscribed onto `session.on_rendered` by `pyjinhx/integrations/fastapi.py:210` and fired once per rendered component from `pyjinhx/rendering.py:428`, storing that component's `RenderedLevel`.

The registry sees only `(type_name, instance_id, entry)`. It cannot distinguish:

- the same logical component re-registering within one request (legitimate — e.g. a component rendered more than once in a pass), from
- two distinct instances that wrongly share a literal `id` (the bug #977 is about).

Both are a same-key write inside one request scope. #985 fixes only the *policy* (debug-gated raise, `InstanceKeyCollisionError`, the session-mediated strict-flag mechanism). Whether #986 additionally needs to narrow the condition — e.g. comparing entry identity, or only raising when the two entries come from different component objects — to avoid false positives on legitimate re-registration is left to #986 to settle at implementation time.

## Test impact (for #986, not done here)

- `tests/pyjinhx/test_instance_registry.py:127-135` (`test_register_instance_duplicate_key_overwrites_last_write_wins`) and `:136-144` (`test_register_instance_duplicate_key_warns_naming_the_key`) currently pin warn-and-overwrite. Under this decision they remain correct **as the non-strict path** and should be kept, with a new sibling test asserting `InstanceKeyCollisionError` when strict dev mode is enabled. #986 owns that change.
- `tests/pyjinhx/test_component.py:461-467` is untouched and must stay green unmodified.

## References

- `pyjinhx/registry.py:60-102` — `register_instance` and its only production caller.
- `pyjinhx/dev.py:23-55` — `_DevConfig`, `enable_reactive_dev`, `_report`: the raise-vs-warn precedent.
- `pyjinhx/config.py:126-142` — `_apply_reactive_dev`: the lazy function-local import pattern (precedent for `config`↔`dev` only — not transferable to `registry`, see Mechanism above).
- `tests/pyjinhx/test_import_graph.py` — `ALLOWED_INTERNAL_IMPORTS["registry"]`, `["dev"]`, `["config"]`, `["session"]`: the declared edge table this decision's mechanism must not violate.
- `pyjinhx/integrations/fastapi.py:210`, `pyjinhx/rendering.py:428` — where the writer is subscribed and fired.
- `docs/superpowers/rebuild/adr/0009-minimal-instance-registry.md` — E7 (single writer), Miss representation (`LookupError`).
- `docs/superpowers/plans/2026-07-29-issue-268.md` — background on the `FixedId`/reserved-name guard #977 protects.
