# Registry

The **instance registry** (`pyjinhx.registry` + `pyjinhx.session`) maps a composite key to a request-scoped component instance or rendered level. It is not wrapped in a class — it is a set of free functions over per-request state.

!!! warning "Internal modules"
    Neither `pyjinhx.registry` nor `pyjinhx.session` is exported from `pyjinhx`, and their
    paths may change. Under `setup(app)` the registry fills itself as components render;
    you only reach for these functions when you are wiring a framework by hand.

Not to be confused with the process-wide tag -> class registry, which is internal machinery documented under [Discovery & Assets](finder.md).

See the [Component Registry guide](../guide/registry.md) for conceptual documentation and usage patterns.

## Instance registry (`pyjinhx.registry` + `pyjinhx.session`)

Request-scoped: entries live only for the duration of a `request_scope()` block and are keyed by a composite of component type name and instance id, so different component types can share the same `id` without collision.

### make_key()

```python
def make_key(type_name: str, instance_id: str) -> str
```

Build the composite registry key for a component type and instance id, e.g. `"PJXButton_btn1"`.

### resolve()

```python
def resolve(type_name: str, instance_id: str) -> object
```

Return the entry registered under this request's composite key — a live instance or a cached `RenderedLevel`, returned as-is. Raises `LookupError` if the key is not registered in this request, including every key when called outside an active `request_scope()`.

### register_instance()

```python
def register_instance(type_name: str, instance_id: str, entry: object) -> None
```

Store an entry in this request's registry under its composite key. The only function that mutates the registry. A call outside `request_scope()` is dropped with a logged warning rather than silently vanishing.

Writing a key that already holds an entry in the same request logs a warning and overwrites (last write wins). With reactive-dev strict mode on (`pyjinhx.dev.enable_reactive_dev(strict=True)` — there is no `PjxSettings` field or `PJX_*` env var that reaches strict mode yet, only this direct call) the same collision raises `pyjinhx.registry.InstanceKeyCollisionError` instead, leaving the existing entry intact — it almost always means two instances of one component class share a hard-coded `id`.

### request_scope()

```python
def request_scope(session: RenderSession | None = None, *, load_context: object | None = None) -> Iterator[RenderSession]
```

Context manager (`pyjinhx.session.request_scope`) that binds fresh per-request state for the duration of the block: the instance registry, dirtied-key tracking, the load cache and its reverse index, and (when given) the app's `context_factory` result readable via `get_load_context()`.

`session` lets a caller wire hooks (e.g. `on_rendered`) onto an existing `RenderSession` before it becomes the one `current_session()` sees as active; when omitted, a fresh `RenderSession()` is constructed.

**Usage:**

```python
from pyjinhx.session import request_scope

with request_scope(load_context=my_app_context) as session:
    # Instances registered here are isolated to this scope
    button = Button(id="submit-btn", text="Submit")
    button.render(session)
# Instance registry, cache, and dirtied keys are automatically restored
```

Scopes support nesting — each scope is independent, and an inner scope that doesn't pass `load_context` leaves the outer scope's value visible. In a FastAPI app, `setup(app)` wires this scope around each request via middleware; see the [FastAPI integration guide](../integrations/fastapi.md#middleware-recommended) for practical examples.
