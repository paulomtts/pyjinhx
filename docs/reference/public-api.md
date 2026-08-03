# Public API Index

Every symbol exported from `pyjinhx` (`__all__`) is listed below with a one-line description and a link to detailed documentation.

These 17 symbols are the entire top-level public API; advanced/internal building blocks (e.g. `oob_swaps`, the load cache, `IntegrationBackend`, the asset-resolver helpers, dev tooling) remain importable from their submodules — e.g. `from pyjinhx.reactive.cache import cache_get`.

The deeper machinery behind these symbols — the parser, finder, asset resolver, integration backend, cache/invalidation, and the Redis/SQLite backends — is documented under **API Reference → Internals**.

## Components & rendering

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `BaseComponent` | Pydantic base class for UI components with Jinja templates | [BaseComponent](../api/base-component.md) |
| `Slot` | Annotated type for a string/component/collection field rendered as raw markup | [BaseComponent](../api/base-component.md) |
| `Children` | Annotated type for the field that receives a tag's nested markup | [BaseComponent](../api/base-component.md) |
| `component()` | Reference an html-only template (no hand-written class) from Python | [BaseComponent](../api/base-component.md#component) |
| `ReactiveComponent` | Base class for dependency-aware reactive components (`react={...}` class keyword + `load()`) | [Reactive API](../api/reactive-api.md) |
| `render()` | Render a component to a finished HTML string | [Renderer](../api/renderer.md) |
| `RenderSession` | Per-render state: Jinja environment, asset accumulation, `on_rendered` hooks | [Renderer](../api/renderer.md) |

## App wiring

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `setup()` | Single-call process + optional FastAPI wiring | [Configuration](../api/config.md#setup) |
| `PjxContext` | Read-only, request-scoped view of session, dirtied keys, and cache state | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md) |

## Reactive authoring

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `mutates()` | Decorator: invalidate cache and accumulate dirtied keys after mutation | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#mutates) |
| `dirty()` | Imperatively dirty reactive keys without decorating a function | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#dirty) |
| `MutationKey` | Base `StrEnum` for app-level reactive key constants | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#mutationkey) |
| `reactive_key()` | Build a reactive key from a type and an instance-key value | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md) |
| `PjxKey` | Marker for `Annotated[..., PjxKey()]` fields stamped as `data-pjx-load` | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#pjxkey) |
| `AppContext` | Subclassable base for an app's per-request context, injected into `load()` | [Mutations, Keys & PjxContext](../api/mutations-keys-context.md) |

## Configuration

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `PjxSettings` | Invalidation backend and reactive dev flags | [Configuration](../api/config.md#pjxsettings) |
| `AssetMode` | Enum: `INLINE` or `NONE` | [Renderer](../api/renderer.md#assetmode) |

## Conceptual guides

For usage patterns and tutorials, see:

- [Usage tiers](../guide/usage-tiers.md) — bare components through full reactive wiring
- [Reactivity](../reactivity.md) — reactive components, OOB swaps, cache scopes
- [Integration Backend](../api/client-backend.md) — the adapter Protocol a framework backend implements, plus request-scoped load context
- [Asset Collection](../guide/assets.md) — delivery modes, dedup, static serving
- [Build an App](../getting-started/build-an-app.md) — end-to-end tutorial
- [FastAPI integration](../integrations/fastapi.md) — request scope, lifespan, headers
