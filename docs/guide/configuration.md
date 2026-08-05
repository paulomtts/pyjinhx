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

Prefer `jinja_globals` and `jinja_filters` on `setup()` for adding names to templates — see [Jinja globals and filters](#jinja-globals-and-filters). Building the session by hand is for the two cases `setup(app)` does not cover: pyjinhx has no backend integration for the framework you are on, or you need to attach `on_rendered` hooks to the session before it goes live.

In those cases, construct a `RenderSession` yourself and bind it for the scope:

```python
from pyjinhx import RenderSession
from pyjinhx.session import request_scope  # not yet public

session = RenderSession()
# session.jinja_env is a standard jinja2.Environment (AbsolutePathLoader,
# autoescape enabled) — add filters, globals, or on_rendered hooks here.

with request_scope(session=session):
    ...
```

`RenderSession()` takes two optional keyword arguments, `jinja_globals=` and `jinja_filters=`, and `request_scope()` takes only `session=` and `load_context=`. A session you build yourself is used as-is: `request_scope()` reads `PjxSettings` for the Jinja mappings only when it has to construct the session itself.

!!! note "Not yet public"
    `RenderSession` is exported from `pyjinhx`; `request_scope` is not — it lives in
    `pyjinhx.session`, outside `pyjinhx.__all__`.

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
- `jinja_globals` — extra names to expose to every template, as a mapping of name to value (default `None`)
- `jinja_filters` — extra filters to expose to every template, as a mapping of filter name to callable (default `None`)

Pass a settings object via `settings=`, or override individual fields with explicit `setup()` keyword arguments. Explicit `setup()` kwargs take precedence over values from `settings=`.

### Jinja globals and filters

`jinja_globals` and `jinja_filters` are the supported way to register names app-wide. Pass them to `setup()` and every request's Jinja environment gets them:

```python
from pyjinhx import setup

setup(app, jinja_globals={"site_name": "Acme"}, jinja_filters={"money": lambda cents: f"${cents / 100:,.2f}"})
```

Templates then read `{{ site_name }}` and `{{ total | money }}` with no per-component wiring.

Both default to `None`, which means "nothing extra to add" — not "start from an empty environment". Jinja seeds its own globals and filters (`range`, `dict`, `|upper`, `|length`, and the rest of the standard library) into every environment first, and these settings are merged on top. Passing `jinja_globals={...}` adds to that seed; it does not replace it. A name that collides with a builtin wins.

There is no environment variable for either field: `PjxSettings.from_env()` reads only the four `PJX_*` variables listed below.

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

Component `load()` results are cached in a request-scoped store: the request scope initializes an empty cache on entry and clears it on exit, so a value loaded once is reused for the rest of that request — this is what dedups the repeated `load()` calls made during the reactive OOB walk. The cache never crosses requests or workers.

See [Reactivity](../reactivity.md).

## Reactive dev mode

Enable development guardrails to catch common reactive mistakes. The supported switch is the
`reactive_dev` setting — pass it to `setup()`, or set `PJX_REACTIVE_DEV=1` in the environment:

```python
from pyjinhx import setup

setup(app, components_root="./components", reactive_dev=True)
```

!!! note "Not yet public"
    The underlying `enable_reactive_dev()` / `disable_reactive_dev()` pair lives in
    `pyjinhx.dev`, which is not exported from `pyjinhx`. Call it directly only for
    `strict=True` (raise instead of log), which the setting does not expose yet:

    ```python
    from pyjinhx.dev import enable_reactive_dev

    enable_reactive_dev(strict=True)  # raise RuntimeError instead of logging
    ```

The one guardrail is `warn_unconsumed_mutations()`: it reports keys this request dirtied that no `load()` in the request declared a dependency on, so dirtying them evicted nothing. `strict=True` raises instead of logging.

Inspect the dependency graph with `dependency_graph()` or `format_dependency_graph()`. See [Mutations, Keys & PjxContext](../api/mutations-keys-context.md#reactive-dev).
