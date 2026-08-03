# Registry

Two unrelated mechanisms, both informally called "the registry": the **class registry** (`pyjinhx.discovery`) maps a template's tag name to the `BaseComponent` subclass that renders it, process-wide; the **instance registry** (`pyjinhx.registry` + `pyjinhx.session`) maps a composite key to a request-scoped instance or rendered level. Neither is wrapped in a class — both are free functions.

See the [Component Registry guide](../guide/registry.md) for conceptual documentation and usage patterns.

## Class registry (`pyjinhx.discovery`)

The tag -> class mapping used to expand `<Card/>`-style tags and to resolve `component()` lookups. Assembled complete off to the side and published in a single locked swap, so no render ever sees a half-built map.

### build_registry()

```python
def build_registry(template_dir: Path | str, classes: Iterable[type]) -> None
```

Walk `template_dir` for `.pjx` templates and publish a fresh tag -> class registry, matching each template to whichever `classes` claims its tag. `setup(components_root=...)` calls this at startup with every declared `BaseComponent` subclass; raises `NotADirectoryError` before any publish happens if the walk fails, leaving the live registry untouched.

### get_class()

```python
def get_class(tag_name: str) -> type | None
```

The component class registered for `tag_name`, or `None`. Never raises on a miss: an unknown tag renders as ordinary markup, verbatim.

### register_class()

```python
def register_class(tag_name: str, cls: type) -> None
```

Publish `cls` under `tag_name` unless the tag already has an owner. The one way a tag is claimed after the import-time build — used by `component()` to register a classless wrapper on demand. A tag that is already owned is left alone: a class registered this way never shadows a declared one; the loser is logged, not silently dropped.

### get_template_dir()

```python
def get_template_dir() -> Path | None
```

The directory the last successful `build_registry()` walked, or `None`. Used by the classless factory (`component()`) to know where to search when no `template_dir` is given explicitly.

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

### request_scope()

```python
def request_scope(
    template_dir: str = "templates",
    session: RenderSession | None = None,
    *,
    load_context: object | None = None,
) -> Iterator[RenderSession]
```

Context manager (`pyjinhx.session.request_scope`) that binds fresh per-request state for the duration of the block: the instance registry, dirtied-key tracking, the load cache and its reverse index, and (when given) the app's `context_factory` result readable via `get_load_context()`.

`session` lets a caller wire hooks (e.g. `on_rendered`) onto an existing `RenderSession` before it becomes the one `current_session()` sees as active; when omitted, a fresh `RenderSession(template_dir)` is constructed.

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
