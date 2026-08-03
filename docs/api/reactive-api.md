# Reactive API

Public symbols for dependency-aware reactive components and HTMX client integration.

See [Reactivity](../reactivity.md) for conceptual documentation and usage patterns.

## ReactiveComponent

```python
class ReactiveComponent(BaseComponent): ...
```

Base class for components that reload from application state via an instance `load()` method and participate in out-of-band HTMX swaps.

### Requirements

- Declare the `react` **class keyword** — a set of `MutationKey` members this component subscribes to: `class Counter(ReactiveComponent, react={Keys.TODOS})`.
- Override `load(self)` to populate `self` from application state. It runs once per request — the first call is memoized in the request-scoped load cache, so later calls in the same request (e.g. from `pjx_mount()` on every recursive render) reuse the result instead of re-fetching.
- For keyed types, declare exactly one `Annotated[..., PjxKey()]` field; its value becomes the load-cache key that identifies which instance `load()` is for.

See [Making builtins reactive](../reactivity.md#making-builtins-reactive) for mixing a `ReactiveComponent` in with a builtin.

### Keyed vs singleton

A class with a `PjxKey`-marked field is **instance-keyed** (e.g. one row per todo) — each distinct field value gets its own cached `load()` result. A class with no `PjxKey` field is a **type-singleton** — one cached result shared by every instance of the class in a request.

Singleton reactive components default `id` to the kebab-cased class name (`TodoCounter` → `"todo-counter"`).

### render()

```python
instance.render(session: RenderSession | None = None) -> str
```

Renders this instance to a finished HTML string, calling `load()` (via `pjx_mount()`) first. This is `BaseComponent.render()` — `ReactiveComponent` adds no separate entry point.

OOB swaps are not produced by `render()` itself. They're composed by `pyjinhx.reactive.response.ReactiveResponse`, which walks the client's `X-PJX-Mounted` manifest against this request's dirtied keys (`walk_manifest()`) and hands the resulting candidates to `oob_swaps()` to build the fan-out fragments appended after the primary markup.

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

Marker for `Annotated[..., PjxKey()]`. The field value becomes this instance's load-cache key.

!!! note "Not yet stamped client-side"
    Nothing server-side currently stamps `data-pjx-type` or `data-pjx-load` — `root_attrs.py` stamps only `data-pjx-id` and `data-pjx-hash` — so a real client-built `X-PJX-Mounted` manifest carries empty `type`/`load` fields today.

## client_script

```python
def client_script() -> Markup
```

Return the pyjinhx client runtime as a `<script>` tag (`from pyjinhx.client import client_script`). It is not part of the top-level public API — root `BaseComponent.render()` injects the runtime automatically unless `X-PJX-Mounted` is already present on the request.

## MountedManifest

```python
class MountedManifest:
    @staticmethod
    def parse(
        mounted: str | list[dict[str, Any]] | object | None,
    ) -> list[dict[str, Any]]: ...

    @staticmethod
    def is_present(client: str | list[dict[str, Any]] | object | None) -> bool: ...
```

`parse()` returns the mounted-region manifest from a request-like object, raw JSON string, or parsed list.

`is_present()` returns whether the client already sent a valid `X-PJX-Mounted` header.

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

`pyjinhx.reactive.response.ReactiveResponse` reads these headers to build the composed body (primary markup plus OOB fragments).

## oob_swaps

```python
def oob_swaps(candidates: list[FanoutCandidate]) -> Markup
```

Compute out-of-band swap fragments for a list of `FanoutCandidate`s, in candidate order. A `"dirty"` candidate emits an `outerHTML:` swap of its already-built markup; a `"missing"` candidate (its keyed `load()` raised `LookupError` — entity removed) emits a delete swap (`delete:[data-pjx-id='…']`) instead. A `"clean"` candidate emits nothing.

Candidates come from `walk_manifest(manifest_entries, dirtied_keys, session=..., primary_html=...)`, which turns a parsed `X-PJX-Mounted` manifest and this request's dirtied keys into the filtered, deduped candidate list — dropping unknown tags, untouched classes, unchanged state hashes, nested regions, and anything the primary response already contains.

`pyjinhx.reactive.response.ReactiveResponse` calls `walk_manifest()` then `oob_swaps()` automatically to compose a reactive request's body. Use them directly only for tests and advanced composition.
