# Configuration

PyJinHx provides several configuration options for customizing template discovery and rendering behavior.

## Template Loading

Templates are resolved per-request through a `RenderSession`, bound for the duration of a `request_scope()` block. There is no global default-environment singleton to configure — you tell the scope where to load templates from when you open it.

### Setting the Template Directory

```python
from pyjinhx.session import request_scope

with request_scope():
    # Components here look for templates under ./components
    ...
```

`template_dir` defaults to `"templates"`.

### Passing a Pre-Built Session

For full control over the underlying Jinja environment, construct a `RenderSession` yourself and hand it to `request_scope()`:

```python
from pyjinhx.session import RenderSession, request_scope

session = RenderSession()
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

- `reactive_dev` — enable reactive dev guardrails (default `False`)
- `inject_htmx` — inline the vendored htmx runtime on reactive root renders (default `True`)
- `components_root` — path to scan for classless components; setting it triggers component discovery (default `None`)
- `static_root` — path to serve static assets from (default `None`)

Pass a settings object via `settings=`, or override individual fields with explicit `setup()` keyword arguments. Explicit `setup()` kwargs take precedence over values from `settings=`.

### Environment variables

`PjxSettings.from_env()` builds settings from the environment:

- `PJX_REACTIVE_DEV` — enables reactive dev mode when set to `1`, `true`, or `yes`
- `PJX_INJECT_HTMX` — controls htmx runtime injection when set to `1`, `true`, or `yes` (default `true`)
- `PJX_COMPONENTS_ROOT` — path that triggers component discovery
- `PJX_STATIC_ROOT` — path to serve static assets from

```python
from pyjinhx import PjxSettings, setup

setup(app, settings=PjxSettings.from_env())
```

See [Configuration API](../api/config.md) for `PjxSettings` and lifespan chaining.

## Load cache scope

Component `load()` results are cached in a request-scoped store: `request_scope()` initializes an empty cache on entry and clears it on exit, so a value loaded once is reused for the rest of that request — this is what dedups the repeated `load()` calls made during the reactive OOB walk. The cache never crosses requests or workers.

See [Reactivity](../reactivity.md).

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
