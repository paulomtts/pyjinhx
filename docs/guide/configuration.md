# Configuration

PyJinHx provides several configuration options for customizing template discovery and rendering behavior.

## Default Environment

The default Jinja environment controls where templates are loaded from.

### Auto-Detection

By default, PyJinHx walks upward from the current directory to find your project root:

```python
from pyjinhx import Renderer

# Auto-detects project root
renderer = Renderer.get_default_renderer()
```

Project root is detected by looking for common markers:

- `pyproject.toml`
- `main.py`
- `README.md`
- `.git`
- `.gitignore`
- `package.json`
- `uv.lock`
- `.venv`

### Setting a Custom Path

```python
from pyjinhx import Renderer

# Set explicit template path
Renderer.set_default_environment("./components")

# Now all components look for templates under ./components
```

### Using a Jinja Environment

For full control, pass a Jinja `Environment`:

```python
from jinja2 import Environment, FileSystemLoader
from pyjinhx import Renderer

env = Environment(
    loader=FileSystemLoader("./templates"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

Renderer.set_default_environment(env)
```

### Clearing the Default

```python
Renderer.set_default_environment(None)  # Reset to auto-detection
```

## Renderer Options

### auto_id

Controls whether component IDs are auto-generated:

```python
# With auto_id=True (default)
renderer = Renderer.get_default_renderer(auto_id=True)
html = renderer.render('<Button text="Click"/>')
# Result: <button id="button-a1b2c3d4...">Click</button>

# With auto_id=False
renderer = Renderer.get_default_renderer(auto_id=False)
html = renderer.render('<Button text="Click"/>')
# Raises ValueError: Missing required "id"
```

### Custom Renderer Instance

Create a renderer with a specific environment:

```python
from jinja2 import Environment, FileSystemLoader
from pyjinhx import Renderer

env = Environment(loader=FileSystemLoader("./my_templates"))
renderer = Renderer(env, auto_id=True)
```

## Project Root Detection

The `Finder` class provides project root detection:

```python
from pyjinhx import Finder

# Auto-detect from current directory
root = Finder.detect_root_directory()

# Start from a specific directory
root = Finder.detect_root_directory(start_directory="/path/to/start")

# Use custom markers
root = Finder.detect_root_directory(
    project_markers=["setup.py", "Makefile", ".project"]
)
```

## Template Extensions

PyJinHx looks for templates with these extensions (in order):

1. `.html`
2. `.jinja`

```
components/
└── button.html    # Found first
└── button.jinja   # Fallback
```

## Registry

Components are automatically registered when their classes are defined.

### Viewing Registered Classes

```python
from pyjinhx import Registry

# Get all registered component classes
classes = Registry.get_classes()
print(classes)  # {'Button': <class 'Button'>, 'Card': <class 'Card'>}
```

### Viewing Registered Instances

```python
from pyjinhx import Registry

button = Button(id="btn1", text="Click")
card = Card(id="card1", title="Hello")

# Get all instances in current context
instances = Registry.get_instances()
print(instances)  # {'btn1': Button(...), 'card1': Card(...)}
```

### Clearing Registries

Useful for testing:

```python
Registry.clear_classes()    # Clear class registry
Registry.clear_instances()  # Clear instance registry
```

!!! note "Context-Local Instances"
    The instance registry is context-local (uses `contextvars`), making it thread-safe for web applications.

## Environment Variables

Currently, PyJinHx does not use environment variables for configuration. All configuration is done programmatically.

## Logging

PyJinHx uses Python's standard logging:

```python
import logging

# Enable debug logging
logging.getLogger("pyjinhx").setLevel(logging.DEBUG)
```

Logged events include:

- Component class registration warnings (duplicates)
- Component instance registration warnings (ID conflicts)
