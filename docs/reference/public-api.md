# Public API Index

Every symbol exported from `pyjinhx` (`__all__`) is listed below with a one-line description and a link to detailed documentation.

## Components & rendering

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `BaseComponent` | Pydantic base class for UI components with Jinja templates | [BaseComponent](../api/base-component.md) |
| `ReactiveComponent` | Base class for dependency-aware reactive components (`reacts_to` + `load()` + `depends_on()`) | [Reactive API](../api/reactive-api.md) |
| `Renderer` | Renders PascalCase tag strings and manages default Jinja environment | [Renderer](../api/renderer.md) |
| `RenderSession` | Per-render asset aggregation state (defined in `pyjinhx.assets`) | [Assets API](../api/assets-api.md) · [Renderer](../api/renderer.md#rendersession) |
| `Parser` | Parses HTML strings into a tree of `Tag` nodes and raw HTML | [Parser & Tag](../api/parser.md) |
| `Tag` | Parsed PascalCase component tag (name, attrs, children) | [Parser & Tag](../api/parser.md#tag) |
| `Finder` | Discovers component templates and asset files on disk | [Finder](../api/finder.md) |
| `Registry` | Class and request-scoped instance registry | [Registry](../api/registry.md) |

## Reactivity

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `client_script()` | Emit the pyjinhx client runtime as a `<script>` tag | [Reactive API](../api/reactive-api.md#client_script) |
| `MountedManifest.is_present()` | Return whether `X-PJX-Mounted` is present on the request | [Reactive API](../api/reactive-api.md#mountedmanifest) |
| `MountedManifest.parse()` | Parse the `X-PJX-Mounted` manifest | [Reactive API](../api/reactive-api.md#mountedmanifest) |
| `LoadedAssets.parse()` | Parse the `X-PJX-Assets` header for asset dedup | [Reactive API](../api/reactive-api.md#loadedassets) |
| `ClientBackend` | ABC for per-request HTTP header access | [Client Backend](../api/client-backend.md#clientbackend) |
| `FastAPIClientBackend` | Default backend for FastAPI/Starlette requests | [Client Backend](../api/client-backend.md) |
| `ClientBackend.scope()` | Set the request-scoped client backend | [Client Backend](../api/client-backend.md#clientbackend) |
| `ClientBackend.current()` | Return the active client backend (manifest, assets, trigger headers) | [Client Backend](../api/client-backend.md#clientbackend) |
| `ClientBackend.reset()` | Clear the request-scoped backend (tests) | [Client Backend](../api/client-backend.md#clientbackend) |
| `ClientBackend.resolve_client()` | Resolve explicit `client=` or fall back to backend | [Client Backend](../api/client-backend.md#auto-resolution-in-render) |
| `oob_swaps()` | Compute HTMX out-of-band swap fragments for dirtied keys | [Reactive API](../api/reactive-api.md#oob_swaps) |
| `PJX_MOUNTED_HEADER` | HTTP header name for the client mounted-region manifest | [Reactive API](../api/reactive-api.md#pjx-headers) |
| `PJX_ASSETS_HEADER` | HTTP header name for asset URLs already loaded in the browser | [Reactive API](../api/reactive-api.md#pjx-headers) |
| `StateKey` | Base `StrEnum` for app-level reactive key constants | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#statekey) |
| `PjxLoad` | Marker for `Annotated[..., PjxLoad()]` fields stamped as `data-pjx-load` | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#pjxload) |
| `MutationTracker` | Request-scoped dirtied-key accumulation | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#mutationtracker) |
| `mutates()` | Decorator: invalidate cache and accumulate dirtied keys after mutation | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#mutates) |
| `TriggerManifest` | Parse `X-PJX-Trigger` (swap-origin region id) | [Reactive API](../api/reactive-api.md) |
| `LoadContext` | Opaque base dataclass for request-scoped `load()` data | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#loadcontext) |
| `LoadContext.current()` | Return the current load context, or `None` | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#loadcontext) |
| `LoadContext.bind()` | Context manager to set the load context | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#loadcontext) |
| `enable_reactive_dev()` | Enable dev guardrails (warnings or strict exceptions) | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#reactive-dev) |
| `disable_reactive_dev()` | Disable dev guardrails | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#reactive-dev) |
| `dependency_graph()` | Map reactive keys to dependent component class names | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#dependency_graph) |
| `format_dependency_graph()` | Format the dependency graph as text or Mermaid | [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#format_dependency_graph) |

## Configuration

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `setup()` | Single-call process + optional FastAPI wiring | [Configuration](../api/config.md#setup) |
| `PyJinhxSettings` | Cache scope, invalidation backend, reactive dev flags | [Configuration](../api/config.md#pyjinhxsettings) |
| `configure_pyjinhx()` | Process-wide startup | [Configuration](../api/config.md#configure_pyjinhx--shutdown_pyjinhx) |
| `shutdown_pyjinhx()` | Process-wide shutdown | [Configuration](../api/config.md#configure_pyjinhx--shutdown_pyjinhx) |
| `pyjinhx_lifespan()` | Sync context manager for tests/scripts | [Configuration](../api/config.md#pyjinhx_lifespan) |

## Load cache & invalidation

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `CacheScope` | Enum: `PROCESS`, `REQUEST`, or `NONE` | [Cache & Invalidation](../api/cache-invalidation.md#cachescope) |
| `LoadCache` | Memoization for reactive `load()` results | [Cache & Invalidation](../api/cache-invalidation.md#loadcache) |
| `LoadCache.scope()` | Return the active load-cache scope | [Cache & Invalidation](../api/cache-invalidation.md#loadcache) |
| `LoadCache.set_scope()` | Set the process-wide load-cache scope | [Cache & Invalidation](../api/cache-invalidation.md#loadcache) |
| `LoadCache.invalidate()` | Evict cached `load()` results for dirtied keys | [Cache & Invalidation](../api/cache-invalidation.md#loadcache) |
| `InvalidationBackend` | ABC for cross-process invalidation fan-out | [Cache & Invalidation](../api/cache-invalidation.md#invalidationbackend) |
| `InvalidationHub` | Runtime coordinator for cross-process invalidation | [Cache & Invalidation](../api/cache-invalidation.md#invalidationhub) |
| `InvalidationHub.set_backend()` | Configure the invalidation backend | [Cache & Invalidation](../api/cache-invalidation.md#invalidationhub) |
| `InvalidationHub.start_listener()` | Start listening for remote invalidations | [Cache & Invalidation](../api/cache-invalidation.md#invalidationhub) |
| `InvalidationHub.stop_listener()` | Stop the invalidation listener | [Cache & Invalidation](../api/cache-invalidation.md#invalidationhub) |

## Assets

| Symbol | Description | Documentation |
|--------|-------------|---------------|
| `AssetMode` | Enum: `INLINE`, `REFERENCE`, or `NONE` | [Renderer](../api/renderer.md#assetmode) |
| `AssetManifest` | Resolved stylesheet and script URLs from a render session | [Assets API](../api/assets-api.md#assetmanifest) |
| `DEFAULT_RUNTIME_URL` | Default public URL for `pjx.js` (`/static/pyjinhx/pjx.js`) | [Assets API](../api/assets-api.md#default_runtime_url) |
| `asset_manifest()` | Build an `AssetManifest` from a `RenderSession` | [Assets API](../api/assets-api.md#asset_manifest) |
| `default_asset_url()` | Map an absolute asset path to a default public URL | [Assets API](../api/assets-api.md#default_asset_url) |
| `hashed_filename()` | Content-hash a filename for cache-busting | [Assets API](../api/assets-api.md#hashed_filename) |
| `Finder.layout_asset_tags()` | Emit `<link>` / `<script>` tags for all discovered component assets | [Assets API](../api/assets-api.md#layout_asset_tags) |
| `make_default_asset_url_resolver()` | Build a resolver using `default_asset_url()` | [Assets API](../api/assets-api.md#make_default_asset_url_resolver) |
| `resolver_with_hash()` | Build a resolver that embeds content hashes in URLs | [Assets API](../api/assets-api.md#resolver_with_hash) |
| `runtime_asset_path()` | Absolute path to the bundled `pjx.js` file | [Assets API](../api/assets-api.md#runtime_asset_path) |

## Conceptual guides

For usage patterns and tutorials, see:

- [Usage tiers](../guide/usage-tiers.md) — bare components through full reactive wiring
- [Reactivity](../reactivity.md) — reactive components, OOB swaps, cache scopes
- [Client Backend](../api/client-backend.md) — per-request header access for `render()`
- [Asset Collection](../guide/assets.md) — delivery modes, dedup, static serving
- [Build an App](../getting-started/build-an-app.md) — end-to-end tutorial
- [FastAPI integration](../integrations/fastapi.md) — request scope, lifespan, headers
