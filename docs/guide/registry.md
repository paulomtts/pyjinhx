# Component Registry

The registry is how PyJinHx tracks component instances, enabling cross-referencing between components in templates.

## How It Works

Instances are registered at **instance creation** (`__init__`):

```python
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str


# When you instantiate, the instance is registered
button = Button(id="submit-btn", text="Submit")
# button is now resolvable via pyjinhx.registry.resolve("Button", "submit-btn")
```

This happens transparently—you don't need to call any registration methods manually.

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
# Request 1: Creates Button(id="submit-btn")
# Request 2: Creates Button(id="submit-btn") → Warning: "already registered; overwriting"
```

### The Solution: Request Scope

Use `request_scope()` to isolate components per request:

```python
from pyjinhx.session import request_scope


@app.get("/")
def index():
    with request_scope():
        # Components here are isolated to this request
        button = Button(id="submit-btn", text="Submit")
        return button.render()
    # Registry automatically cleaned up
```

On entry, `request_scope()` binds a fresh `RenderSession`, clears pending mutations, and initializes the request-tier load cache. On exit — even when an exception occurs — it restores the previous state.

`request_scope(template_dir="templates", session=None, *, load_context=None)` takes an optional `template_dir` for where a newly-constructed `RenderSession` loads templates from, an optional pre-built `session` to bind instead, and an optional `load_context` — the app's `context_factory` result for this request, readable via `get_load_context()`.

For application-wide coverage, pyjinhx ships no middleware of its own. Prefer `setup(app, ...)`, which registers middleware that opens a `request_scope()` for you (see the [canonical FastAPI snippet](../integrations/fastapi.md#middleware-recommended)). To wire it by hand instead, open the scope yourself:

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

Discovery finds classes by scanning the filesystem for `.pjx` templates, not by any side effect of defining a class — a component only becomes tag-resolvable once it has a matching template file. The instance registry enables cross-referencing in templates.

### Template context precedence

During render, registered instances are injected into the Jinja context by `id` so templates can reference them by registry key. A component cannot cross-reference a component of the **same type and id** that is currently being rendered — such a reference renders empty and logs a warning. Different component types that share the same `id` are tracked independently, so nesting an `InnerChip(id="x")` inside an `OuterShell(id="x")` renders both in full. **Component field values from `model_dump()` take precedence** when a field name collides with an instance `id` (registry injection uses `setdefault`). Watch for this with `ReactiveComponent`, whose `id` defaults to the kebab-cased class name: a `Total` reactive component with a `total` field defaults its `id` to `"total"`, so the field would shadow the instance. (A plain `BaseComponent` defaults to `pjx-<n>` — not the kebab-class default that reactive components get.)

```python
from pyjinhx.registry import make_key, resolve

# Instance registry (automatic when you instantiate, inside a request_scope())
btn = MyButton(id="test")
key = make_key("MyButton", "test")
assert resolve("MyButton", "test") is btn
```
