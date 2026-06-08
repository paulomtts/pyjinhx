# Client Backend

Per-request HTTP header access for reactive rendering. Wire once in middleware; `render()` reads `X-PJX-Mounted` and `X-PJX-Assets` automatically.

## ClientBackend

```python
class ClientBackend(ABC):
    def get_header(self, name: str) -> str | None: ...
```

Abstract base — implement for non-FastAPI frameworks if needed.

## FastAPIClientBackend

```python
class FastAPIClientBackend(ClientBackend):
    def __init__(self, request: object) -> None: ...
```

Default implementation for FastAPI and Starlette. Wraps `request.headers`. The instance exposes `.headers.get()` for `render()` duck typing.

## fastapi_client_backend

```python
def fastapi_client_backend(request: object) -> FastAPIClientBackend
```

Factory — use this in middleware:

```python
from pyjinhx import Registry, fastapi_client_backend

with Registry.request_scope(
    client_backend=fastapi_client_backend(request),
):
    ...
```

## Auto-resolution in render()

When `client=` and `mounted=` are omitted:

| Parameter | Resolved from backend when |
|-----------|---------------------------|
| `client` | Backend is set (runtime skip, asset dedup) |
| `mounted` | Backend is set **and** (`dirtied` passed or `@mutates` left pending dirtied) |

Explicit `client=` / `mounted=` always override the backend.
