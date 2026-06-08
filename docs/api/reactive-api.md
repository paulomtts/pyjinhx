# Reactive API

Public symbols for dependency-aware reactive components and HTMX client integration.

See [Reactivity](../reactivity.md) for conceptual documentation and usage patterns.

## ReactiveComponent

```python
class ReactiveComponent(BaseComponent):
    reacts_to: ClassVar[frozenset[str]]
    load_reads: ClassVar[frozenset[str]] = frozenset()
```

Base class for components that reload from application state via a `load()` classmethod and participate in out-of-band HTMX swaps.

### Requirements

- Declare `reacts_to` — the reactive keys this component depends on (collection-tier stems like `"todos"` or instance-tier stems like `"todo"`).
- Implement `load()` as a `@classmethod` that returns a fresh component instance.
- Optionally declare `load_reads` for dev-mode validation (keys read inside `load()` must be covered by `reacts_to`).

### Keyed vs singleton

Set `_pjx_keyed = True` on instance-keyed components (e.g. one row per todo). Singleton components omit the key.

Singleton reactive components default `id` to the kebab-cased class name (`TodoCounter` → `"todo-counter"`); `load()` need not set one unless you want a custom id.

### render()

Two forms coexist via a descriptor:

**Class method (route entry point):**

```python
Cls.render(key=None, *, dirtied=None, mounted=None, client=None) -> Markup
```

Auto-`load()`s the primary component, renders it, and appends OOB swaps for dependents. With `ClientBackend` wired in middleware, omit `mounted` and `client` on mutation routes — headers are read from the backend after `@mutates`.

**Instance method:**

```python
instance.render(*, dirtied=None, mounted=None, client=None) -> Markup
```

Render an already-built instance as the primary without re-loading from the world.

!!! note "Without ClientBackend"
    Pass `mounted=request` (and `client=request` for asset dedup) when not using a request-scoped backend. See [Client Backend](client-backend.md).

### effective_reacts_to()

```python
def effective_reacts_to(self) -> set[str]
```

Runtime reactive keys this loaded instance depends on. Defaults to the interpolated
static `reacts_to` declaration. Override to narrow based on instance state (static
`reacts_to` must remain a superset). Used by `oob_swaps` after `load()` and by
`LoadCache` reverse indexing.

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

## client_script

```python
def client_script(*, mode: AssetMode | None = None, src: str | None = None) -> Markup
```

Return the pyjinhx client runtime as a `<script>` tag. Use in raw Jinja shells outside
the component render path. Root `BaseComponent.render()` calls inject the runtime
automatically unless `X-PJX-Mounted` is already present on the request.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mode` | `AssetMode.INLINE` | `INLINE` inlines source; `REFERENCE` emits `<script src="...">` |
| `src` | Renderer runtime URL | Public URL when mode is `REFERENCE` |

## MountedManifest

```python
class MountedManifest:
    @staticmethod
    def parse(mounted: str | list[dict[str, Any]] | object | None) -> list[dict[str, Any]]: ...

    @staticmethod
    def is_present(client: str | list[dict[str, Any]] | object | None) -> bool: ...
```

`parse()` returns the mounted-region manifest from a request-like object, raw JSON string, or parsed list.

`is_present()` returns whether the client already sent a valid `X-PJX-Mounted` header. A JSON array (including `[]`) means `pjx.js` is active; missing or malformed values mean the runtime should be injected on root full-page renders.

## PJX headers

| Constant | Value | Purpose |
|----------|-------|---------|
| `PJX_MOUNTED_HEADER` | `"X-PJX-Mounted"` | JSON manifest of mounted reactive regions (`id`, `type`, `hash`) |
| `PJX_ASSETS_HEADER` | `"X-PJX-Assets"` | JSON list of asset URLs already loaded in the browser |

The client runtime (`pjx.js`) sets both headers on HTMX requests. With [ClientBackend](client-backend.md) wired in middleware, `render()` reads them automatically; otherwise pass the request as `mounted=` and `client=`.

## LoadedAssets

```python
class LoadedAssets:
    @staticmethod
    def parse(client: str | list[str] | object | None) -> frozenset[str]: ...
```

Parse the client-reported list of asset URLs for REFERENCE-mode asset dedup.

Accepts a request-like object (`.headers.get(PJX_ASSETS_HEADER)`), a raw JSON string, a parsed list/tuple/set of URL strings, or `None`/`""` (nothing loaded).

Used internally when a client source is resolved for `render()` with asset dedup enabled (explicit `client=` or `ClientBackend`).

## oob_swaps

```python
def oob_swaps(
    dirtied: set[ReactiveKey],
    mounted: str | list[dict[str, Any]] | object | None,
    *,
    exclude_ids: set[str] | None = None,
) -> Markup
```

Compute out-of-band swap fragments for every mounted reactive region whose declared dependencies intersect the dirtied keys.

**Behavior:**

1. Evicts dirtied keys from the load cache.
2. Walks the client manifest (`X-PJX-Mounted`).
3. Reloads each matching dependent via `load()`.
4. Emits an OOB swap only when the fresh `state_hash()` differs from the client's reported hash.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `dirtied` | State keys the route mutated (e.g. `{"todos"}` or `{"todo:42"}`) |
| `mounted` | Request object, raw header string, parsed manifest list, or `None` |
| `exclude_ids` | Mounted ids to skip (typically the primary response id) |

`ReactiveComponent.render()` calls this automatically. Use directly only for advanced partial-response composition.
