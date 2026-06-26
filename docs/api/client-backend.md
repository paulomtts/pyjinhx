# Client Backend

Per-request HTTP header access for reactive rendering. Wire once in your app's middleware; `render()` reads `X-PJX-Mounted` and `X-PJX-Assets` from the active backend. `X-PJX-Trigger` is client-only — consumed by pjx.js for loading indicators, not by the server render walk.

PyJinHx does **not** ship middleware — you define a thin wrapper (see [FastAPI integration](../integrations/fastapi.md#middleware-recommended)) that calls `Registry.request_scope(client_backend=FastAPIClientBackend(request))`.

## ClientBackend

```python
class ClientBackend(ABC):
    def get_header(self, name: str) -> str | None: ...

    @classmethod
    def current(cls) -> ClientBackend | None: ...

    @classmethod
    def scope(cls, backend: ClientBackend | None) -> ContextManager[None]: ...

    @classmethod
    def reset(cls) -> None: ...

    @classmethod
    def resolve_client(cls, explicit: object | None) -> object | None: ...
```

Abstract base — implement for non-FastAPI frameworks if needed.

| Class method | Purpose |
|--------------|---------|
| `current()` | Return the active backend for this request, or `None`. |
| `scope(backend)` | Set the request-scoped backend (usually via `Registry.request_scope`). |
| `reset()` | Clear the backend. Mainly for tests. |
| `resolve_client(explicit)` | Return `explicit` if set, else `current()`. Used by `_render()` for asset dedup. |

## FastAPIClientBackend

Defined in `pyjinhx.integrations.fastapi`:

```python
class FastAPIClientBackend(ClientBackend):
    def __init__(self, request: object) -> None: ...
```

Default implementation for FastAPI and Starlette. Wraps `request.headers`. `setup(app, ...)` wires this automatically in middleware.

## Auto-resolution in render()

When a `ClientBackend` is active (via `setup()` middleware or `ClientBackend.scope()`):

- Root renders use it for asset dedup (`X-PJX-Assets`) and runtime injection gating (`X-PJX-Mounted`).
- Reactive class/instance `render()` reads the `X-PJX-Mounted` manifest for OOB swaps.

Mutation routes call `Cls.render(*args)` with no framework kwargs — pending keys from `@mutates` drive the OOB walk.

Without a `ClientBackend`, reactive OOB is skipped even when mutations are pending — only the primary is rendered.

## Non-FastAPI frameworks

Subclass `ClientBackend` and implement `get_header()`. Pass the instance to `Registry.request_scope(client_backend=...)`.

## `apply_response_directives(response)`

Called by the integration when finalizing a response. The default applies the
`HX-*` headers implied by the request's `ResponseDirectives` (e.g.
`HX-Reswap: none` for an OOB-only `ReactiveResponse`) to any response whose
`.headers` is a mutable mapping. Override only if your framework's response
header API differs. This is how a custom `ClientBackend` inherits pyjinhx's
reactive response behavior.

See the [htmx integration guide](../integrations/htmx.md) for when a custom backend needs this.
