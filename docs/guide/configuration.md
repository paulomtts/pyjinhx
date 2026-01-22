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
