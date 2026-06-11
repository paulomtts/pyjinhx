# Public API Index

Every symbol exported from `pyjinhx` (`__all__`) is listed below with a one-line description and a link to detailed documentation.

These 11 symbols are the entire top-level public API; advanced/internal building blocks (e.g. `oob_swaps`, `LoadCache`, `ClientBackend`, the asset-resolver helpers, dev tooling) remain importable from their submodules — e.g. `from pyjinhx.cache import LoadCache`.

## Components & rendering

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `BaseComponent` | Pydantic base class for UI components with Jinja templates | [BaseComponent](../api/base-component.md) |
| `ReactiveComponent` | Base class for dependency-aware reactive components (`react={...}` class keyword + `load()` + `depends_on()`) | [Reactive API](../api/reactive-api.md) |
| `Renderer` | Renders PascalCase tag strings and manages default Jinja environment | [Renderer](../api/renderer.md) |

## App wiring

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `setup()` | Single-call process + optional FastAPI wiring | [Configuration](../api/config.md#setup) |
| `Registry` | Class and request-scoped instance registry | [Registry](../api/registry.md) |

## Reactive authoring

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `mutates()` | Decorator: invalidate cache and accumulate dirtied keys after mutation | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#mutates) |
| `MutationKey` | Base `StrEnum` for app-level reactive key constants | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#mutationkey) |
| `PjxKey` | Marker for `Annotated[..., PjxKey()]` fields stamped as `data-pjx-load` | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#pjxkey) |
| `PjxContext` | Opaque base dataclass for request-scoped `load()` data | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#pjxcontext) |

## Configuration

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `PjxSettings` | Invalidation backend and reactive dev flags | [Configuration](../api/config.md#pjxsettings) |
| `AssetMode` | Enum: `INLINE`, `REFERENCE`, or `NONE` | [Renderer](../api/renderer.md#assetmode) |

## Conceptual guides

For usage patterns and tutorials, see:

- [Usage tiers](../guide/usage-tiers.md) — bare components through full reactive wiring
- [Reactivity](../reactivity.md) — reactive components, OOB swaps, cache scopes
- [Client Backend](../api/client-backend.md) — per-request header access for `render()`
- [Asset Collection](../guide/assets.md) — delivery modes, dedup, static serving
- [Build an App](../getting-started/build-an-app.md) — end-to-end tutorial
- [FastAPI integration](../integrations/fastapi.md) — request scope, lifespan, headers
