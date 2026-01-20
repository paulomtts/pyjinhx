# Registry

Central registry for component classes and instances.

## Overview

The `Registry` maintains two registries:

- **Class Registry**: Maps component class names to their types (process-wide)
- **Instance Registry**: Maps component IDs to instances (context-local, thread-safe)

Components are automatically registered when defined and instantiated.

## API Reference

::: pyjinhx.Registry
    options:
      members:
        - register_class
        - get_classes
        - clear_classes
        - register_instance
        - get_instances
        - clear_instances
      show_root_heading: true
      heading_level: 3

## Usage Examples

### Viewing Registered Classes

```python
from pyjinhx import BaseComponent, Registry


class Button(BaseComponent):
    id: str
    text: str


class Card(BaseComponent):
    id: str
    title: str


# Classes are auto-registered
classes = Registry.get_classes()
print(classes)
# {'Button': <class 'Button'>, 'Card': <class 'Card'>}
```

### Viewing Registered Instances

```python
from pyjinhx import Registry

button = Button(id="btn1", text="Click")
card = Card(id="card1", title="Hello")

# Instances are auto-registered
instances = Registry.get_instances()
print(instances)
# {'btn1': Button(...), 'card1': Card(...)}
```

### Cross-Referencing in Templates

Registered instances are available in template context:

```html
<!-- In any component template -->
<div>
    <!-- Reference another component by ID -->
    {{ btn1 }}
</div>
```

### Clearing for Tests

```python
import pytest
from pyjinhx import Registry


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    Registry.clear_classes()
    Registry.clear_instances()
```

## How It Works

### Class Registration

When you define a `BaseComponent` subclass, `__init_subclass__` automatically registers it:

```python
class Button(BaseComponent):  # Registered as "Button"
    id: str
    text: str
```

### Instance Registration

When you instantiate a component, `__init__` registers it by ID:

```python
button = Button(id="my-btn", text="Click")
# Now accessible as Registry.get_instances()["my-btn"]
```

### Thread Safety

The instance registry uses `contextvars`, making it:

- Thread-safe for multi-threaded web servers
- Request-scoped in async frameworks like FastAPI
- Isolated between concurrent requests

## Duplicate Handling

### Duplicate Class Names

If a class with the same name is registered twice, a warning is logged and the new class overwrites the old:

```python
class Button(BaseComponent):  # First registration
    id: str
    text: str


class Button(BaseComponent):  # Warning logged, overwrites
    id: str
    label: str
```

### Duplicate Instance IDs

If an instance with the same ID is registered twice, a warning is logged and the new instance overwrites:

```python
btn1 = Button(id="submit", text="Submit")
btn2 = Button(id="submit", text="Cancel")  # Warning logged
```
