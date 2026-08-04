# Component Registry

The registry is how PyJinHx tracks component instances, enabling cross-referencing between components in templates.

## How It Works

The registry is a low-level primitive in `pyjinhx.registry`, backed by a per-request `ContextVar`. Instantiating a component registers nothing; entries appear when a component is *rendered*, or when you add one yourself with `register_instance()`:

```python
from pyjinhx import BaseComponent
from pyjinhx.registry import register_instance


class Button(BaseComponent):
    id: str
    text: str


button = Button(id="submit-btn", text="Submit")
register_instance("Button", button.id, button)
# button is now resolvable via pyjinhx.registry.resolve("Button", "submit-btn")
```

!!! note "Registration is automatic under `setup(app)`"
    `pyjinhx.registry` also exports `register_rendered_instance()`, shaped for `RenderSession.on_rendered`. `PjxScopeMiddleware` — the middleware `setup(app)` installs — subscribes it on the session it builds for each request, so under a wired app every rendered component lands in that request's registry under `ComponentName_id`, holding its `RenderedLevel`. Outside that wiring (a bare `RenderSession`, a hand-rolled `request_scope()`), subscribe it yourself or call `register_instance()` explicitly for whatever you want resolvable.

### Composite Keys

The registry stores components using a composite key of `ComponentName_id`. This means:

- A `Button` with `id="main"` is stored as `Button_main`
- A `Card` with `id="main"` is stored as `Card_main`

`pyjinhx.registry.make_key(type_name, instance_id)` builds this key.

!!! tip
    **Different component types can share the same `id`** without collision.

## Registry Scoping

### The Problem

In web applications, component instances from one request can persist and affect subsequent requests:

```python
# Request 1: register_instance("Button", "submit-btn", button)
# Request 2: register_instance("Button", "submit-btn", button) → Warning: "already registered; overwriting"
```

### The Solution: Request Scope

Use `request_scope()` to isolate components per request:

```python
from pyjinhx.session import request_scope
from pyjinhx.registry import register_instance


@app.get("/")
def index():
    with request_scope():
        # Components registered here are isolated to this request
        button = Button(id="submit-btn", text="Submit")
        register_instance("Button", button.id, button)
        return button.render()
    # Registry automatically cleaned up
```

On entry, `request_scope()` binds a fresh `RenderSession`, clears pending mutations, and initializes the request-tier load cache. On exit — even when an exception occurs — it restores the previous state.

`request_scope(session=None, *, load_context=None)` takes an optional pre-built `session` to bind instead of a fresh one — which is how you attach `on_rendered` hooks before the session goes live — and an optional `load_context`, the app's `context_factory` result for this request, readable via `get_load_context()`. There is no template-directory argument: sessions carry no components root, and templates resolve per component class (see [Configuration](configuration.md#template-loading)).

For application-wide coverage, prefer `setup(app, ...)`: it installs `PjxScopeMiddleware`, which opens a `request_scope()` per request, subscribes the render hooks, and parses the pjx request headers onto the session (see the [canonical FastAPI snippet](../integrations/fastapi.md#middleware-recommended)). To wire it by hand instead, open the scope yourself:

```python
from pyjinhx import setup
from pyjinhx.session import request_scope

setup(app)  # recommended
# or:
with request_scope():
    ...
```

### Nested Scopes

Scopes can be nested—each creates its own isolated registry:

```python
with request_scope():
    outer = Button(id="outer", text="Outer")

    with request_scope():
        # "outer" is not visible here
        inner = Button(id="inner", text="Inner")

    # "inner" is not visible here, "outer" is restored
```

## Common Patterns

### Checking Registration

```python
from pyjinhx.registry import make_key, resolve

# Check if a specific component exists (using the composite key)
key = make_key("Button", "submit-btn")
button = resolve("Button", "submit-btn")  # raises LookupError if not registered
```

### Same ID, Different Types

Different component types can use the same `id`:

```python
class Card(BaseComponent):
    id: str
    title: str


class Modal(BaseComponent):
    id: str
    title: str


# Both can use id="main" without collision
card = Card(id="main", title="Card Title")
modal = Modal(id="main", title="Modal Title")

# Both are resolvable independently
assert resolve("Card", "main") is card
assert resolve("Modal", "main") is modal
```

!!! note "HTML IDs"
    While the registry allows same IDs across types, remember that HTML `id` attributes must be unique in the DOM. Use distinct IDs if both components render on the same page.

## Component Discovery vs Instance Registry

PyJinHx separates how component *classes* are found from how component *instances* are tracked:

| Mechanism | Scope | Purpose |
|-----------|-------|---------|
| **Template discovery** | Process-wide | Walks `.pjx` template files on disk to map tag names to component classes |
| **Instance registry** | Context-local | Maps composite keys to instances (e.g., `"Button_submit"` → instance) |

Discovery finds classes by scanning `components_root` for `.pjx` templates plus every declared class that already resolved a template of its own — a component only becomes tag-resolvable once it has a matching template file. The instance registry enables cross-referencing in templates; entries arrive as components render under a wired app, or explicitly (see [How It Works](#how-it-works) above).

```python
from pyjinhx.registry import make_key, register_instance, resolve

btn = MyButton(id="test")
register_instance("MyButton", btn.id, btn)  # inside a request_scope()
key = make_key("MyButton", "test")
assert resolve("MyButton", "test") is btn
```
