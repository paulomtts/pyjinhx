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

## Load cache scope

Control where reactive `load()` results are cached:

```python
from pyjinhx import CacheScope, set_load_cache_scope

set_load_cache_scope(CacheScope.PROCESS)  # default — shared per worker
set_load_cache_scope(CacheScope.REQUEST)  # isolated per request scope
set_load_cache_scope(CacheScope.NONE)     # no caching
```

`Registry.request_scope()` initializes a request-scoped cache on entry and clears it on exit. With `PROCESS` scope, reads also use the process-wide store; with `REQUEST` scope, only the request store is used.

See [Cache & Invalidation](../api/cache-invalidation.md) and [Reactivity](../reactivity.md).

## Invalidation fan-out

When using `CacheScope.PROCESS` with multiple workers, configure an `InvalidationBackend` so cache evictions propagate across processes:

```python
from pyjinhx import (
    set_invalidation_backend,
    start_invalidation_listener,
    stop_invalidation_listener,
)

set_invalidation_backend(my_backend)
start_invalidation_listener()
# ... on shutdown:
stop_invalidation_listener()
```

See [Cache & Invalidation](../api/cache-invalidation.md) and the [FastAPI integration](../integrations/fastapi.md) lifespan example.

## Reactive dev mode

Enable development guardrails to catch common reactive mistakes:

```python
from pyjinhx import enable_reactive_dev, disable_reactive_dev

enable_reactive_dev()           # log warnings
enable_reactive_dev(strict=True)  # raise RuntimeError instead
disable_reactive_dev()
```

Guardrails cover: mutations without a consuming `render()`, dirtied keys without `mounted`, and `load_reads` not covered by `reacts_to`.

Inspect the dependency graph with `dependency_graph()` or `format_dependency_graph()`. See [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#reactive-dev).
