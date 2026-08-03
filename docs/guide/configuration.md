# Configuration

PyJinHx provides several configuration options for customizing template discovery and rendering behavior.

## Template Loading

Templates are resolved per-request through a `RenderSession`, bound for the duration of a `request_scope()` block. There is no global default-environment singleton to configure — you tell the scope where to load templates from when you open it.

### Setting the Template Directory

```python
from pyjinhx.session import request_scope

with request_scope(template_dir="./components"):
    # Components here look for templates under ./components
    ...
```

`template_dir` defaults to `"templates"`.

### Passing a Pre-Built Session

For full control over the underlying Jinja environment, construct a `RenderSession` yourself and hand it to `request_scope()`:

```python
from pyjinhx.session import RenderSession, request_scope

session = RenderSession(template_dir="./templates")
# session.jinja_env is a standard jinja2.Environment (FileSystemLoader,
# autoescape enabled) — attach hooks like on_rendered before binding it.

with request_scope(session=session):
    ...
```

When `session` is given, `template_dir` is ignored.

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

setup(app, context_factory=lambda req: AppLoadContext(db=get_db(req)))
```

`PjxSettings` has these fields:

- `invalidation_backend` — cross-worker invalidation backend (default `None`)
- `reactive_dev` — enable reactive dev guardrails (default `False`)
- `inject_htmx` — inline the vendored htmx runtime on reactive root renders (default `True`)
- `htmx_redirects` — adapt `3xx` redirects to `204 + HX-Redirect` for htmx requests (default `False`); the browser navigates instead of swapping the destination into a fragment, `Set-Cookie` is preserved, and `304` is left alone

The load-cache scope is **derived** from `invalidation_backend`: a backend (e.g. Redis) makes cross-request caching safe across workers, so `load()` results are cached per worker process; without one, they are cached per request only — the only multi-worker-safe default.

Pass a settings object via `settings=`, or override individual fields with explicit `setup()` keyword arguments. Explicit `setup()` kwargs take precedence over values from `settings=`.

### Environment variables

`PjxSettings.from_env()` builds settings from the environment:

- `REDIS_URL` — wires a `RedisInvalidationBackend` (which derives cross-request caching)
- `PJX_INVALIDATION_DB` — wires a `SqliteInvalidationBackend` with the given path (used when `REDIS_URL` is not set)
- `PJX_REACTIVE_DEV` — enables reactive dev mode when set to `1`, `true`, or `yes`
- `PJX_HTMX_REDIRECTS` — enables htmx redirect adaptation when set to `1`, `true`, or `yes`

```python
from pyjinhx import PjxSettings, setup

setup(app, settings=PjxSettings.from_env())
```

See [Configuration API](../api/config.md) for `PjxSettings`, lifespan chaining, and cache defaults.

## Load cache scope

You don't pick a scope — it follows the backend. By default (no `invalidation_backend`), `load()` results are cached **per request only**, the only multi-worker-safe behavior. Configure a cross-worker backend to opt into cross-request caching per worker process:

```python
from pyjinhx import setup

setup(app)  # per-request caching (default, multi-worker safe)
setup(app, invalidation_backend=...)  # cross-request per worker; see integrations.redis
```

`request_scope()` initializes a request-scoped cache on entry and clears it on exit. With a backend configured, reads also use the process-wide store; otherwise only the request store is used. Within-request caching always happens — it dedups the repeated `load()` calls of the reactive OOB walk.

See [Cache & Invalidation](../api/cache-invalidation.md) and [Reactivity](../reactivity.md).

## Invalidation fan-out

For multi-worker production, set a cross-worker `invalidation_backend` so `invalidate()` fans out to every process (and enables cross-request caching):

```python
from pyjinhx import PjxSettings, setup
from pyjinhx.integrations.redis import RedisInvalidationBackend

setup(
    app,
    settings=PjxSettings(
        invalidation_backend=RedisInvalidationBackend("redis://..."),
    ),
)
```

See [Cache & Invalidation](../api/cache-invalidation.md) and [Redis integration](../api/integrations-redis.md).

## Reactive dev mode

Enable development guardrails to catch common reactive mistakes:

```python
from pyjinhx.dev import enable_reactive_dev, disable_reactive_dev

enable_reactive_dev()  # log warnings
enable_reactive_dev(strict=True)  # raise RuntimeError instead
disable_reactive_dev()
```

Guardrails cover: mutations without a consuming `render()` and dirtied keys without `mounted`.

Inspect the dependency graph with `dependency_graph()` or `format_dependency_graph()`. See [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#reactive-dev).
