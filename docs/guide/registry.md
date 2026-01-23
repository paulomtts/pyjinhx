# Component Registry

The registry is how PyJinHx tracks component instances, enabling cross-referencing between components in templates.

## How It Works

When you instantiate a component, it's automatically registered:

```python
from pyjinhx import BaseComponent, Registry

class Button(BaseComponent):
    id: str
    text: str

# This component is now in the registry
button = Button(id="submit-btn", text="Submit")
```

The registry stores components using a composite key of `ComponentName_id`. This means:

- A `Button` with `id="main"` is stored as `Button_main`
- A `Card` with `id="main"` is stored as `Card_main`

!!! tip
    **Different component types can share the same `id`** without collision.

## Registry Scoping

### The Problem

In web applications, component instances from one request can persist and affect subsequent requests:

```python
# Request 1: Creates Button(id="submit-btn")
# Request 2: Creates Button(id="submit-btn") → Warning: "Overwriting..."
```

### The Solution: Request Scope

Use `Registry.request_scope()` to isolate components per request:

```python
from pyjinhx import Registry

@app.get("/")
def index():
    with Registry.request_scope():
        # Components here are isolated to this request
        button = Button(id="submit-btn", text="Submit")
        return button.render()
    # Registry automatically cleaned up
```

For application-wide coverage, use middleware:

```python
from starlette.middleware.base import BaseHTTPMiddleware

class RegistryScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        with Registry.request_scope():
            return await call_next(request)

app.add_middleware(RegistryScopeMiddleware)
```

### Nested Scopes

Scopes can be nested—each creates its own isolated registry:

```python
with Registry.request_scope():
    outer = Button(id="outer", text="Outer")

    with Registry.request_scope():
        # "outer" is not visible here
        inner = Button(id="inner", text="Inner")

    # "inner" is not visible here, "outer" is restored
```

## Common Patterns

### Clearing the Registry

For testing or resetting state:

```python
Registry.clear_instances()  # Remove all component instances
```

### Checking Registration

```python
# Get all registered instances
instances = Registry.get_instances()

# Check if a specific component exists (using the composite key)
key = Registry.make_key("Button", "submit-btn")
if key in instances:
    button = instances[key]
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

# Both are in the registry
assert len(Registry.get_instances()) == 2
```

!!! note "HTML IDs"
    While the registry allows same IDs across types, remember that HTML `id` attributes must be unique in the DOM. Use distinct IDs if both components render on the same page.

## Class Registry vs Instance Registry

PyJinHx maintains two separate registries:

| Registry | Scope | Purpose |
|----------|-------|---------|
| **Class registry** | Process-wide | Maps class names to types (e.g., `"Button"` → `Button`) |
| **Instance registry** | Context-local | Maps composite keys to instances (e.g., `"Button_submit"` → instance) |

The class registry enables the `Renderer` to instantiate components from PascalCase tags. The instance registry enables cross-referencing in templates.

```python
# Class registry (automatic when you define a class)
class MyButton(BaseComponent):
    id: str

assert "MyButton" in Registry.get_classes()

# Instance registry (automatic when you instantiate)
btn = MyButton(id="test")
key = Registry.make_key("MyButton", "test")
assert key in Registry.get_instances()
```
