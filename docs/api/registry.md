# Registry

Central registry for component classes and instances.

## Class

### Registry

Provides two registries:

- **Class registry**: Maps component class names to their types (process-wide)
- **Instance registry**: Maps composite keys (`ComponentName_id`) to instances (context-local, thread-safe)

Component classes are auto-registered when subclassing `BaseComponent`. Instances are registered upon instantiation using a composite key that combines the class name and instance ID. This allows different component types to share the same `id` without collision.

See the [Component Registry guide](../guide/registry.md) for conceptual documentation and usage patterns.

## Class Registry Methods

### register_class()

```python
@classmethod
def register_class(cls, component_class: type[BaseComponent]) -> None
```

Register a component class by its name. Called automatically when subclassing `BaseComponent`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `component_class` | `type[BaseComponent]` | The component class to register |

### get_classes()

```python
@classmethod
def get_classes(cls) -> dict[str, type[BaseComponent]]
```

Return a copy of all registered component classes.

**Returns:** Dictionary mapping class names to component class types.

### clear_classes()

```python
@classmethod
def clear_classes(cls) -> None
```

Remove all registered component classes. Useful for testing.

## Instance Registry Methods

### make_key()

```python
@classmethod
def make_key(cls, class_name: str, instance_id: str) -> str
```

Generate a registry key from component class name and instance ID.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `class_name` | `str` | The component class name (e.g., `"Button"`) |
| `instance_id` | `str` | The component instance ID (e.g., `"submit-btn"`) |

**Returns:** The composite key string (e.g., `"Button_submit-btn"`).

**Example:**

```python
from pyjinhx import Registry

key = Registry.make_key("Button", "submit-btn")
# Returns: "Button_submit-btn"

# Check if a component exists
if key in Registry.get_instances():
    button = Registry.get_instances()[key]
```

### register_instance()

```python
@classmethod
def register_instance(cls, component: BaseComponent) -> None
```

Register a component instance by its ID. Called automatically on instantiation.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `component` | `BaseComponent` | The component instance to register |

### get_instances()

```python
@classmethod
def get_instances(cls) -> dict[str, BaseComponent]
```

Return all registered component instances in the current context.

**Returns:** Dictionary mapping composite keys (`ComponentName_id`) to component instances. Use `make_key()` to construct keys for lookup.

### clear_instances()

```python
@classmethod
def clear_instances(cls) -> None
```

Remove all registered component instances from the current context.

### request_scope()

```python
@classmethod
@contextmanager
def request_scope(cls)
```

Context manager for request-scoped component instances.

Creates a fresh instance registry on entry and restores the previous state on exit. This is useful in web applications where each request should have an isolated registry to prevent components from one request leaking into another.

**Usage:**

```python
from pyjinhx import Registry

with Registry.request_scope():
    # Components registered here are isolated to this scope
    button = Button(id="submit-btn", text="Submit")
    # ... render template
# Registry automatically restored to previous state
```

**Features:**

- Creates a fresh empty registry on entry
- Restores previous registry state on exit (even if an exception occurs)
- Supports nesting—each scope is independent
- Prevents "Overwriting..." warnings when reusing component IDs across requests

See the [FastAPI integration guide](../integrations/fastapi.md#request-scoped-registry) for practical examples.
