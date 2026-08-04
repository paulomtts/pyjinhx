# Configuration

PyJinHx provides several configuration options for customizing template discovery and rendering behavior.

## Template Loading

There is no template directory to configure and no search root to set. A component's template is found from the component itself: `<snake_case>.pjx` beside the module that defines the class, walking up the inheritance chain until a file exists. By the time Jinja is involved the path is already fully resolved, so `RenderSession`'s environment uses an `AbsolutePathLoader` — a loader that treats every template name as an absolute filesystem path and has no root and no relative fallback.

### Pointing pyjinhx at your components

What *is* configurable is where pyjinhx scans for classless components — `.pjx` files with no Python class of their own — so their PascalCase tags become resolvable:

```python
from pyjinhx import setup

setup(app, components_root="./components")
```

`components_root` triggers discovery: every `.pjx` under it is walked and mapped to a tag, alongside every declared component class that already resolves a template of its own. Declared classes work with no `components_root` at all.

To build one classless component out of a directory the scan doesn't cover, pass the directory to `component()` directly:

```python
from pyjinhx import component

Sidebar = component("Sidebar", template_dir="./widgets")  # reads ./widgets/sidebar.pjx
```

### Passing a Pre-Built Session

For full control over the underlying Jinja environment — or to attach `on_rendered` hooks before the session goes live — construct a `RenderSession` yourself and hand it to `request_scope()`:

```python
from pyjinhx.session import RenderSession, request_scope

session = RenderSession()
# session.jinja_env is a standard jinja2.Environment (AbsolutePathLoader,
# autoescape enabled) — add filters, globals, or on_rendered hooks here.

with request_scope(session=session):
    ...
```

`RenderSession()` takes no arguments, and `request_scope()` takes only `session=` and `load_context=`.

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
- `inject_htmx` — recorded only today; nothing reads it, so the vendored htmx runtime ships with `pjx.js` either way (default `True`)
- `components_root` — path to scan for classless components; setting it triggers component discovery (default `None`)
- `static_root` — path to serve static assets from (default `None`)

Pass a settings object via `settings=`, or override individual fields with explicit `setup()` keyword arguments. Explicit `setup()` kwargs take precedence over values from `settings=`.

### Environment variables

`PjxSettings.from_env()` builds settings from the environment:

- `PJX_REACTIVE_DEV` — enables reactive dev mode when set to `1`, `true`, or `yes`
- `PJX_INJECT_HTMX` — sets the `inject_htmx` field when set to `1`, `true`, or `yes` (default `true`)
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

The one guardrail is `warn_unconsumed_mutations()`: it reports keys this request dirtied that no `load()` in the request declared a dependency on, so dirtying them evicted nothing. `strict=True` raises instead of logging.

Inspect the dependency graph with `dependency_graph()` or `format_dependency_graph()`. See [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#reactive-dev).
