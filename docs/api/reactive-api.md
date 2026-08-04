# Reactive API

Public symbols for dependency-aware reactive components and HTMX client integration.

See [Reactivity](../reactivity.md) for conceptual documentation and usage patterns.

## ReactiveComponent

```python
class ReactiveComponent(BaseComponent): ...
```

Base class for components that rebuild themselves from application state via a `load()` factory and participate in out-of-band HTMX swaps.

### Requirements

- Declare the `react` **class keyword** — a set of `MutationKey` members this component subscribes to: `class Counter(ReactiveComponent, react={Keys.TODOS})`.
- Override `load()` as a **classmethod factory** that returns an instance:

    ```python
    class ItemRow(ReactiveComponent, react={Keys.TODOS}):
        todo_id: Annotated[int, PjxKey()]
        title: str = ""

        @classmethod
        def load(cls, todo_id: int) -> "ItemRow":
            todo = STORE[todo_id]  # KeyError here is the delete signal — see below
            return cls(todo_id=todo_id, title=todo.text)
    ```

    An instance method `def load(self)` raises `TypeError` at class-definition time. `load()` runs once per request — the first call is memoized in the request-scoped load cache, so later calls in the same request (e.g. from mounting the same instance again during recursive render) reuse the result instead of re-fetching.

- For keyed types, declare exactly one `Annotated[..., PjxKey()]` field. Its value becomes the load-cache key, and it is passed to `load()` as a parameter of the same name.

!!! warning "Raising is part of `load()`'s contract"
    A `LookupError` out of `load()` is the **sole** signal that a region no longer exists, and it is what produces the delete swap `<div hx-swap-oob="delete:[data-pjx-id='…']"></div>`. `KeyError` and `IndexError` subclass `LookupError`, so an ordinary lookup against your own store already says the right thing — do not catch it. A `load()` that swallows the store's `KeyError` and returns a field-default instance gets its region swapped with a **blank render** instead of deleted.

See [Making builtins reactive](../reactivity.md#making-builtins-reactive) for mixing a `ReactiveComponent` in with a builtin.

### Keyed vs singleton

A class with a `PjxKey`-marked field is **instance-keyed** (e.g. one row per todo) — each distinct field value gets its own cached `load()` result. A class with no `PjxKey` field is a **type-singleton** — one cached result shared by every instance of the class in a request.

There is no per-class `id` default: an unset `id` becomes the auto id `pjx-<n>`, which changes from render to render. A reactive region has to stay addressable across requests, so always pass an explicit, stable `id` where the instance is constructed — `<Counter id="counter"/>` in a template, `ItemRow(todo_id=todo.id, id=f"row-{todo.id}")` from a handler. `load()` does not need to set it: on a fan-out rebuild the id is restored from the manifest entry, because it identifies the mounted region rather than the loaded data.

### render()

```python
instance.render(session: RenderSession | None = None) -> str
```

Renders this instance to a finished HTML string, calling `load()` first. This is `BaseComponent.render()` — `ReactiveComponent` adds no separate entry point.

`render()` returns one component's markup and nothing else — it never appends OOB swaps. Fan-out belongs to the response composer: **returning** a component from a handler is what gets dependents swapped, because [`pyjinhx.responses.compose()`](responses.md) walks the client's `X-PJX-Mounted` manifest against this request's dirtied keys (`walk_manifest()`) and hands the resulting candidates to `oob_swaps()` to build the fragments appended after the primary markup. This happens on every composed response; there is nothing to opt into.

### state_hash()

```python
def state_hash(self) -> str
```

SHA-256 of canonical sorted JSON from `model_dump(mode="json")` with
`state_hash_exclude` applied (`id` excluded by default on `ReactiveComponent`).
Used by OOB swap gating — override for custom hashing.

```python
state_hash_exclude: ClassVar[frozenset[str]] = frozenset({"id"})
```

## PjxKey

```python
class PjxKey: ...
```

Marker for `Annotated[..., PjxKey()]`. The field value becomes this instance's load-cache key, and it is stamped on the rendered root as `data-pjx-load` so the client can name the region back.

`data-pjx-load` round-trips through an HTML attribute as a string, but the framework validates it back to the field's **declared** type before calling `load()`. A key declared `todo_id: int` arrives in `load()` as an `int` — do not coerce it yourself.

### Root attributes

`stamp_reactive_root_attrs`, subscribed to `RenderSession.on_rendered` by `PjxScopeMiddleware`, splices four attributes onto every reactive component's root tag:

| Attribute | Value |
|-----------|-------|
| `data-pjx-id` | The component's `id` |
| `data-pjx-type` | The snake_case **tag** name (`TodoCounter` → `todo_counter`) |
| `data-pjx-hash` | `state_hash()` at render time |
| `data-pjx-load` | The PjxKey field's value — only on keyed classes |

`data-pjx-reacts` is **not** stamped. `pjx.js` only reads it, so an author who wants the loading-indicator behaviour has to render it on the root themselves.

## Client runtime

```python
def inject_runtime(session: RenderSession, request: Any = None) -> None
```

`from pyjinhx.client.inject import inject_runtime`. Records the inline pjx.js runtime (plus vendored htmx and the loading artifacts) on `session` for a cold render. The integration backend calls it from `to_response()` before composing, and only for a component return — every other shape is a fragment. It no-ops when the request already carries `X-PJX-Mounted`, when this session was injected once already, or when JS is not delivered inline (`AssetMode.INLINE`). You do not normally call it: `setup(app)` wires it.

## MountedManifest

```python
class MountedManifest:
    @staticmethod
    def parse(
        mounted: str | list[dict[str, Any]] | object | None,
    ) -> list[dict[str, Any]]: ...
```

`parse()` returns the mounted-region manifest from a request-like object, raw JSON string, or parsed list. Anything unreadable yields an empty list, which fan-out reads as "nothing is mounted" — a full render rather than a failed one.

## TriggerManifest

```python
class TriggerManifest:
    @staticmethod
    def parse(
        client: str | dict[str, Any] | object | None,
    ) -> dict[str, Any] | None: ...
```

Parse `X-PJX-Trigger` — the `data-pjx-id` of the element that started the HTMX request.

## PJX headers

| Constant | Value | Purpose |
|----------|-------|---------|
| `PJX_MOUNTED_HEADER` | `"X-PJX-Mounted"` | JSON manifest of mounted regions (`id`, `type`, `hash`, optional `load`) |
| `PJX_TRIGGER_HEADER` | `"X-PJX-Trigger"` | JSON `{"id": "<data-pjx-id>"}` of the swap origin |
| `PJX_ASSETS_HEADER` | `"X-PJX-Assets"` | JSON list of the asset tokens the client already has |

`PjxScopeMiddleware` parses these headers onto the request's session (`session.pjx_mounted`, `session.pjx_trigger`, `session.pjx_assets`); [`compose()`](responses.md) then reads them off the session to build the composed body (primary markup plus OOB fragments).

## oob_swaps

```python
def oob_swaps(candidates: list[FanoutCandidate]) -> Markup
```

Compute out-of-band swap fragments for a list of `FanoutCandidate`s, in candidate order. A `"dirty"` candidate emits an `outerHTML:` swap of its already-built markup; a `"missing"` candidate (its keyed `load()` raised `LookupError` — entity removed) emits a delete swap (`delete:[data-pjx-id='…']`) instead. A `"clean"` candidate emits nothing.

A miss in the request-scoped instance registry is **not** a "missing" candidate — out-of-primary regions miss it routinely. Only `LookupError` out of `load()` produces a delete.

Candidates come from `walk_manifest(manifest_entries, dirtied_keys, session=..., primary_html=...)`, which turns a parsed `X-PJX-Mounted` manifest and this request's dirtied keys into the filtered, deduped candidate list — dropping unknown tags, untouched classes, unchanged state hashes, nested regions, and anything the primary response already contains.

[`compose()`](responses.md) calls `walk_manifest()` then `oob_swaps()` automatically on every response it builds. Use them directly only for tests and advanced composition.
