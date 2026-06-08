# Client Backend

Per-request HTTP header access for reactive rendering. Wire once in your app's middleware; `render()` reads `X-PJX-Mounted` and `X-PJX-Assets` automatically.

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

    @classmethod
    def resolve_mounted(
        cls, explicit: object | None, *, dirtied: object | None
    ) -> object | None: ...
```

Abstract base — implement for non-FastAPI frameworks if needed.

| Class method | Purpose |
|--------------|---------|
| `current()` | Return the active backend for this request, or `None`. |
| `scope(backend)` | Set the request-scoped backend (usually via `Registry.request_scope`). |
| `reset()` | Clear the backend. Mainly for tests. |
| `resolve_client(explicit)` | Return `explicit` if set, else `current()`. Used by `render()`. |
| `resolve_mounted(explicit, dirtied=...)` | Return `explicit` if set; else `current()` only when reactive mode applies (see below). |

## FastAPIClientBackend

Defined in `pyjinhx.integrations.fastapi` (re-exported from `pyjinhx`):

```python
class FastAPIClientBackend(ClientBackend):
    def __init__(self, request: object) -> None: ...
```

Default implementation for FastAPI and Starlette. Wraps `request.headers`. The instance exposes `.headers.get()` for `render()` duck typing. `setup(app, ...)` wires this automatically in middleware.

## Auto-resolution in render()

When `client=` and `mounted=` are omitted:

| Parameter | Resolved from backend when |
|-----------|---------------------------|
| `client` | Backend is set (runtime skip, asset dedup) |
| `mounted` | Backend is set **and** (`dirtied` passed or `@mutates` left pending dirtied) |

Explicit `client=` / `mounted=` always override the backend.

### Mutation-only `mounted` rule

`mounted` is **not** auto-resolved on every request. It applies only when the render is reactive — i.e. `dirtied` is passed (including via pending `@mutates` keys) — so hx-boost full-page GETs do not accidentally enter the OOB swap path.

## Non-FastAPI frameworks

Subclass `ClientBackend` and implement `get_header()`. Pass the instance to `Registry.request_scope(client_backend=...)`. The backend instance should expose `.headers.get()` for duck typing, or pass `mounted=` / `client=` explicitly on each `render()` call.
