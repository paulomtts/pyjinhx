# Integration Backend

The interface a framework adapter implements to wire pyjinhx into an app, and the per-request seam that carries request state into `render()`.

PyJinHx ships one adapter, `pyjinhx.integrations.fastapi`, and this interface is what a Flask, bare-WSGI, or other adapter would implement to plug in the same way.

## IntegrationBackend

```python
class IntegrationBackend(Protocol):
    def is_installed(self, app: object) -> bool: ...
    def mark_installed(self, app: object) -> None: ...
    def mount_static(self, app: object, directory: str) -> None: ...
    def on_startup(self, app: object) -> None: ...
    def on_shutdown(self, app: object) -> None: ...
    def to_response(self, result: object, request: object | None) -> object: ...
```

What a framework adapter provides so `setup()` can wire pyjinhx in.

| Method | Purpose |
|--------|---------|
| `is_installed(app)` | Whether setup has already been applied to `app`, so a re-entrant `setup()` doesn't stack two scopes or two lifespans on one request. |
| `mark_installed(app)` | Record that setup has been applied to `app`. |
| `mount_static(app, directory)` | Serve the files in `directory` at `/static` on `app`. |
| `on_startup(app)` | Run pyjinhx's configure step as `app` starts. |
| `on_shutdown(app)` | Run pyjinhx's shutdown step as `app` stops. |
| `to_response(result, request)` | Adapt a pjx handler return into the framework's response type. Non-pjx results pass through untouched. |

Route adaptation is deliberately absent from this interface — turning a handler's pjx return into a framework response is `to_response()`, but *wiring* that onto routes differs enough per framework (FastAPI swaps `APIRoute` subclasses, Flask would use an `after_request` hook) that each backend owns its own wiring.

## register_backend / get_backend

```python
def register_backend(backend: IntegrationBackend) -> None
def get_backend() -> IntegrationBackend | None
```

`register_backend()` publishes the adapter that `setup(app=...)` dispatches through — one slot, since a process wires pyjinhx into one app. `get_backend()` returns the registered adapter, or `None` when no adapter module was imported.

## Request-scoped load context

A backend binds one `request_scope(load_context=...)` (from `pyjinhx.session`) per request around its handler. The `load_context` is whatever the app's `context_factory` derives from the framework's native request object — headers, auth info, whatever a component's `load()` needs.

```python
from pyjinhx.integrations.base import load_context_for

load_context = load_context_for(request, context_factory)
with request_scope(load_context=load_context) as session:
    ...
```

Inside the scope, `get_load_context()` returns that value for the life of the request:

```python
from pyjinhx.session import get_load_context


def load(self):
    request = get_load_context()
```

## Non-FastAPI frameworks

Implement `IntegrationBackend` for your framework and call `register_backend()` with an instance, mirroring `pyjinhx.integrations.fastapi`. See the [FastAPI integration](../integrations/fastapi.md) source for a complete example of wiring `request_scope()`, header parsing, and `to_response()`.
