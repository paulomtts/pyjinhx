# Client Backend

Framework-agnostic access to HTTP request headers for reactive rendering. Wire once per request in middleware; `render()` reads `X-PJX-Mounted` and `X-PJX-Assets` automatically.

## ClientBackend

```python
class ClientBackend(ABC):
    def get_header(self, name: str) -> str | None: ...
```

Abstract base for reading headers on the current request.

## RequestClientBackend (default for FastAPI / Starlette)

```python
class RequestClientBackend(HeadersClientBackend):
    def __init__(self, request: object) -> None: ...
```

Wraps any request object with `.headers.get(name)`. No `fastapi` import in core.

## client_backend_from_request

```python
def client_backend_from_request(request: object) -> RequestClientBackend
```

Factory for the default ASGI request backend.

## Request scope wiring

```python
from pyjinhx import Registry, client_backend_from_request

with Registry.request_scope(
    load_context=...,
    client_backend=client_backend_from_request(request),
):
    ...
```

Or use `ClientBackendMiddleware.bind_client_backend` inside a Starlette/FastAPI `BaseHTTPMiddleware`.

## Auto-resolution in render()

When `client=` and `mounted=` are omitted:

| Parameter | Resolved from backend when |
|-----------|---------------------------|
| `client` | Backend is set (runtime skip, asset dedup) |
| `mounted` | Backend is set **and** (`dirtied` passed or `@mutates` left pending dirtied) |

Explicit `client=` / `mounted=` always override the backend.

## HeadersClientBackend

```python
class HeadersClientBackend(ClientBackend):
    def __init__(self, headers: Mapping[str, str]) -> None: ...
```

For tests or non-ASGI contexts with a plain header mapping.
