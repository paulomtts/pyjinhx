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
- `.git`
- `.gitignore`
- `package.json`
- `uv.lock`

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

## Application setup

For web apps, use a single call:

```python
from pyjinhx import setup

setup(app, load_context_factory=lambda req: AppLoadContext(db=get_db(req)))
```

`PyJinhxSettings` has three fields:

- `cache_scope` — load cache scope (default `CacheScope.REQUEST`)
- `invalidation_backend` — cross-process invalidation backend (default `None`)
- `reactive_dev` — enable reactive dev guardrails (default `False`)

Pass a settings object via `settings=`, or override individual fields with explicit `setup()` keyword arguments. Explicit `setup()` kwargs take precedence over values from `settings=`.

### Environment variables

`PyJinhxSettings.from_env()` builds settings from the environment:

- `PJX_LOAD_CACHE_SCOPE` — cache scope name (default `request`)
- `PJX_REACTIVE_DEV` — enables reactive dev mode when set to `1`, `true`, or `yes`
- `REDIS_URL` — wires a `RedisInvalidationBackend`, but only when the cache scope is `process`

```python
from pyjinhx import PyJinhxSettings, setup

setup(app, settings=PyJinhxSettings.from_env())
```

See [Configuration API](../api/config.md) for `PyJinhxSettings`, lifespan chaining, and cache defaults.

## Load cache scope

Default is **`CacheScope.REQUEST`** (multi-worker safe). Opt into cross-request caching:

```python
from pyjinhx import CacheScope, setup

setup(app, cache_scope=CacheScope.PROCESS, invalidation_backend=...)  # see integrations.redis
setup(app, cache_scope=CacheScope.NONE)
```

`Registry.request_scope()` initializes a request-scoped cache on entry and clears it on exit. With `PROCESS` scope, reads also use the process-wide store; with `REQUEST` scope, only the request store is used.

See [Cache & Invalidation](../api/cache-invalidation.md) and [Reactivity](../reactivity.md).

## Invalidation fan-out

When using `CacheScope.PROCESS` with multiple workers, configure an `InvalidationBackend`:

```python
from pyjinhx import CacheScope, PyJinhxSettings, setup
from pyjinhx.integrations.redis import RedisInvalidationBackend

setup(
    app,
    settings=PyJinhxSettings(
        cache_scope=CacheScope.PROCESS,
        invalidation_backend=RedisInvalidationBackend("redis://..."),
    ),
)
```

See [Cache & Invalidation](../api/cache-invalidation.md) and [Redis integration](../api/integrations-redis.md).

## Reactive dev mode

Enable development guardrails to catch common reactive mistakes:

```python
from pyjinhx import enable_reactive_dev, disable_reactive_dev

enable_reactive_dev()           # log warnings
enable_reactive_dev(strict=True)  # raise RuntimeError instead
disable_reactive_dev()
```

Guardrails cover: mutations without a consuming `render()`, dirtied keys without `mounted`, and `depends_on()` outside the static `reacts_to` superset.

Inspect the dependency graph with `dependency_graph()` or `format_dependency_graph()`. See [Mutations, Keys & LoadContext](../api/mutations-keys-context.md#reactive-dev).
