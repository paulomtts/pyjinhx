# Reactive API

Public symbols for dependency-aware reactive components and HTMX client integration.

See [Reactivity](../reactivity.md) for conceptual documentation and usage patterns.

## ReactiveComponent

```python
class ReactiveComponent(BaseComponent):
    reacts_to: ClassVar[set[str]]
```

Base class for components that reload from application state via a `load()` classmethod and participate in out-of-band HTMX swaps.

### Requirements

- Declare `reacts_to` — **state keys** this component subscribes to (e.g. `"todos"`).
- Implement `load()` as a `@classmethod` that returns a fresh component instance.
- For keyed `load(cls, resource)` types, declare exactly one `Annotated[..., PjxKey()]` field.

### Keyed vs singleton

A parameter after `cls` in `load()` makes the type **instance-keyed** (e.g. one row per todo). Declare `PjxKey` on the resource field. Zero-arg `load(cls)` is a type-singleton.

Singleton reactive components default `id` to the kebab-cased class name (`TodoCounter` → `"todo-counter"`).

### render()

Two forms coexist via a descriptor:

**Class method (route entry point):**

```python
Cls.render(*args, **kwargs) -> Markup
```

Auto-`load()`s the primary, renders it, and appends OOB swaps when a `ClientBackend` is active and `@mutates` left pending keys.

Raises `TypeError` if called with arguments on a type-singleton, or without the key argument on an instance-keyed type.

**Instance method:**

```python
instance.render() -> Markup
```

Render an already-built instance as the primary without re-loading from the world.

### depends_on()

```python
def depends_on(self) -> set[str]
```

Reactive state keys this loaded instance depends on. Defaults to static `reacts_to`. Override to narrow for load-cache indexing (static `reacts_to` must remain a superset). `oob_swaps` matches on static `reacts_to` only.

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
class PjxKey:
    ...
```

Marker for `Annotated[..., PjxKey()]`. The field value is stamped as `data-pjx-load` and returned in the client manifest as `load`.

## client_script

```python
def client_script(*, mode: AssetMode | None = None, src: str | None = None) -> Markup
```

Return the pyjinhx client runtime as a `<script>` tag (`from pyjinhx.client import client_script`). It is not part of the top-level public API — root `BaseComponent.render()` injects the runtime automatically unless `X-PJX-Mounted` is already present on the request.

## MountedManifest

```python
class MountedManifest:
    @staticmethod
    def parse(mounted: str | list[dict[str, Any]] | object | None) -> list[dict[str, Any]]: ...

    @staticmethod
    def is_present(client: str | list[dict[str, Any]] | object | None) -> bool: ...
```

`parse()` returns the mounted-region manifest from a request-like object, raw JSON string, or parsed list.

`is_present()` returns whether the client already sent a valid `X-PJX-Mounted` header.

## TriggerManifest

```python
class TriggerManifest:
    @staticmethod
    def parse(client: str | dict[str, Any] | object | None) -> dict[str, Any] | None: ...
```

Parse `X-PJX-Trigger` — the `data-pjx-id` of the element that started the HTMX request.

## PJX headers

| Constant | Value | Purpose |
|----------|-------|---------|
| `PJX_MOUNTED_HEADER` | `"X-PJX-Mounted"` | JSON manifest of mounted regions (`id`, `type`, `hash`, optional `load`) |
| `PJX_ASSETS_HEADER` | `"X-PJX-Assets"` | JSON list of asset URLs already loaded |
| `PJX_TRIGGER_HEADER` | `"X-PJX-Trigger"` | JSON `{"id": "<data-pjx-id>"}` of the swap origin |

Wire [ClientBackend](client-backend.md) via `setup()`; `render()` reads headers from the active backend.

## LoadedAssets

```python
class LoadedAssets:
    @staticmethod
    def parse(client: str | list[str] | object | None) -> frozenset[str]: ...
```

Parse `X-PJX-Assets` for REFERENCE-mode asset dedup on root renders.

## oob_swaps

```python
def oob_swaps(
    dirtied: set[ReactiveKey],
    mounted: str | list[dict[str, Any]] | object | None,
    *,
    exclude_ids: set[str] | None = None,
    skip_invalidate: bool = False,
) -> Markup
```

Compute out-of-band swap fragments for every mounted reactive region whose `reacts_to` intersects `dirtied`.

When a keyed `load(manifest.load)` raises `LookupError` (entity removed), emits a delete OOB swap (`delete:[data-pjx-id='…']`) instead of failing.

`ReactiveComponent.render()` calls this automatically when reactive mode is active. Use directly only for tests and advanced composition.
