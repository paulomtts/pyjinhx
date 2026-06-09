# Claude Code

You can use the following skill as a [custom slash command](https://docs.anthropic.com/en/docs/claude-code/slash-commands) in Claude Code to help the AI build with PyJinHx.

## Setup

Create a file at `.claude/commands/pyjinhx.md` in your project root with the following content:

````markdown
---
name: pyjinhx
description: Build reusable, type-safe UI components with PyJinHx (Pydantic + Jinja2)
---

You are building with PyJinHx — a Python library for reusable, type-safe UI components using Pydantic + Jinja2.

## Core Concepts

Components = Python class (Pydantic BaseModel) + Jinja2 template file (same directory).

```python
from pyjinhx import BaseComponent

class Card(BaseComponent):
    id: str              # Required on all components
    title: str
    subtitle: str = ""   # Optional with default
```

Extra fields passed to a component are accepted and available in the template context (not validated).

## Template Discovery

Templates are auto-discovered from the class name. They must be in the **same directory** as the Python file.

| Class Name     | Template File                                          |
|----------------|--------------------------------------------------------|
| `Button`       | `button.html` or `button.jinja`                       |
| `ActionButton` | `action_button.html` or `action-button.html` (or `.jinja`) |

## Rendering

**Two ways to render:**

1. **Python-side** — instantiate and call `.render()`:
```python
button = Button(id="submit", text="Submit")
html = button.render()
```

2. **String-side** — PascalCase tags in HTML strings:
```python
from pyjinhx import Renderer
renderer = Renderer.get_default_renderer()
html = renderer.render('<Button id="submit" text="Submit"/>')
```

PascalCase tag resolution order:
1. Registered instance (matching ID) — reuses and updates props
2. Registered class (matching tag name) — creates new instance with Pydantic validation
3. Generic fallback — uses BaseComponent with auto-discovered template, no validation

Inner content of tags becomes the `{{ content }}` template variable.

## Templates

Templates receive all component fields as variables. Use full Jinja2 syntax. **PascalCase tags work inside templates too** — PyJinHx expands them automatically during rendering, so you can compose components declaratively:

```html
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {% if subtitle %}<p>{{ subtitle }}</p>{% endif %}
    <Button id="card-action" text="Click me"/>
</div>
```

This means any `.html` or `.jinja` template — whether a component template, a page template, or a string passed to `renderer.render()` — can contain `<PascalCase/>` tags that get resolved to components.

## Nesting

Nested components are wrapped in `NestedComponentWrapper`. Render with `{{ child }}`, access props with `{{ child.props.field }}`.

```python
class Card(BaseComponent):
    id: str
    title: str
    action: Button  # Single nested component
    items: list[Button]  # List of components
    widgets: dict[str, Button]  # Dict of components
```

```html
{{ action }}                          {# renders the nested component #}
{{ action.props.text }}               {# access nested props #}
{% for item in items %}{{ item }}{% endfor %}
{% for key, val in widgets.items() %}{{ val }}{% endfor %}
```

Lists and dicts can mix components with strings. Nesting depth is unlimited.

## Assets (JS & CSS)

Place kebab-case `.js` and/or `.css` files next to the component. They are auto-collected, deduplicated per render session, and injected at the root render — CSS as `<style>` before the HTML, JS as `<script>` after.

| Class Name     | JS File             | CSS File             |
|----------------|---------------------|----------------------|
| `Button`       | `button.js`         | `button.css`         |
| `ActionButton` | `action-button.js`  | `action-button.css`  |

Each component gets its own `<script>`/`<style>` tag (errors in one don't break others). Add extra files via the `js` and `css` fields:

```python
widget = MyWidget(id="w1", js=["path/to/extra.js"], css=["path/to/theme.css"])
```

Missing extra files emit a warning (check `pyjinhx` logger). For production, use `AssetMode.REFERENCE` with `Renderer.set_asset_url_resolver()`. Disable assets with `AssetMode.NONE`. Use `Finder(root).collect_javascript_files()` / `Finder(root).collect_css_files()` or `layout_asset_tags()` for layout preload.

**Kebab vs snake for co-located assets:** `pascal_case_to_kebab_case(ClassName) + ".js"|".css"` (e.g. `TabGroup` → `tab-group.js`, `LoadingOverlay` → `loading-overlay.js`). Wrong stem (e.g. `tab_group.js`) is **not** collected.

## Reactivity (dependency-aware OOB swaps)

Declare each component's state dependencies once; a mutation route re-emits exactly the
mounted regions that depend on what changed (HTMX out-of-band swaps). "Reactivity" here
is **cache invalidation, not signals** — server-side, no client watchers.

Subclass `ReactiveComponent` and declare **both** `reacts_to` and a `load()` classmethod
(both enforced — missing `load()` can't instantiate; missing `reacts_to` is a
definition-time error):

```python
from typing import Annotated, ClassVar
from pyjinhx import PjxLoad, ReactiveComponent, mutates

class Counter(ReactiveComponent):
    remaining: int
    reacts_to: ClassVar[set[str]] = {"todos"}   # state keys you name (not ids/types)

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())     # id defaults to "counter"
```

- **`reacts_to`** — arbitrary state-key strings *you* choose (`"todos"`). The server
  intersects a component's `reacts_to` with pending `@mutates` keys to decide what to
  swap (and what to evict from the `load()` cache).
- **`load()`** — rebuilds the component from the current world, independent of any route.
- **`id`** auto-defaults to the **kebab-cased class name** (`Counter` → `"counter"`);
  pass an explicit `id` for instance-keyed regions (e.g. `id=f"row-{todo_id}"`).
- `state_hash()` gates swaps: a region is re-sent only if its fresh hash differs from
  the one the client reported.
- Roots are auto-stamped with `data-pjx-id` / `data-pjx-type` / `data-pjx-hash` /
  `data-pjx-reacts` (the space-joined `reacts_to` keys, which `pjx.js` reads to scope
  loading indicators) — plus `data-pjx-load` when keyed via `PjxLoad`. A reactive component
  **must render a single root element**.

### Mutation routes return `render()` — nothing else

A mutation route does exactly one thing: **`return <component>.render(...)`**. You never
call `load()` and never assemble swaps yourself. Decorate store methods with `@mutates`
on **state keys only**:

```python
@mutates("todos")
def toggle_all():
    ...

@app.post("/todos/toggle")
def toggle():
    store.toggle_all()
    return Counter.render()
```

`render` has two forms (one name):

- **Class form (route entry)** — `Cls.render(*args, **kwargs)` for keyed types,
  `Cls.render()` for singletons: auto-`load()`s the primary, renders it as the HTMX
  main-target response, then appends OOB swaps for every *other* mounted reactive region
  whose `reacts_to` intersects pending `@mutates` keys. **Only the primary is excluded**
  from OOB (HTMX already swaps it as the main response); the trigger region is **not**
  excluded — a clicked region that depends on the dirtied keys updates itself OOB like any
  other dependent (e.g. a "Clear completed (N)" button refreshing its own count).
  `X-PJX-Trigger` is **client-only** (used by `pjx.js` for loading indicators); the server
  OOB walk reads the mounted manifest, never the trigger header.
- **Instance form** — `instance.render()`: plain render of an already-built instance
  (no re-`load()`).

Wire `setup(app, ...)` so `ClientBackend` is active — mutation routes need no `mounted`
or `client` kwargs. `pjx.js` sends `X-PJX-Mounted`, `X-PJX-Assets`, and `X-PJX-Trigger`
on every HTMX request.

`oob_swaps(dirtied, mounted)` is exported for tests/advanced use; routes use `render()`.

### Instance-keyed regions (rows)

A component is **instance-keyed iff `load()` takes one argument after `cls`**. Declare
exactly one `Annotated[..., PjxLoad()]` field — its value is stamped as `data-pjx-load`
and returned in the manifest as `load` for OOB reloads.

```python
class TodoItemRow(ReactiveComponent):
    todo_id: Annotated[int, PjxLoad()]
    title: str = ""
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls, todo_id: int | str) -> "TodoItemRow":
        tid = int(todo_id)
        t = store.get(tid)
        return cls(id=f"row-{tid}", todo_id=tid, title=t.text)

@app.post("/rows/{todo_id}/toggle")
def toggle_row(todo_id: int):
    store.toggle(todo_id)
    return TodoItemRow.render(todo_id)
```

- **`render(todo_id)` → `load(todo_id)`** automatically. Set explicit `id` in `load()` for
  stable DOM targets (e.g. `row-42`). Templates use the `PjxLoad` field:
  `hx-post="/rows/{{ todo_id }}/toggle"`.
- **`@mutates("todos")`** on store methods dirties collection-tier state; OOB pub-sub reloads
  every mounted region whose `reacts_to` intersects, with hash-gating skipping unchanged regions.
- **Removed entities:** if a keyed `load(manifest.load)` raises `LookupError`, OOB emits a
  `delete:[data-pjx-id='…']` swap (e.g. after clear-completed removes rows still in the manifest).

### Client runtime & cache

- Root full-page renders auto-inject `pjx.js` unless the request already carries
  `X-PJX-Mounted`. For a raw Jinja shell, use `{{ client_script() }}` in `<head>`.
- **Loading indicators (v0.7.1):** put `data-pjx-loading="skeleton"` (or `"spinner"`) on any
  element inside a reactive root template. While an in-flight request dirties keys the region
  `reacts_to`, `pjx.js` flags those elements (matched via the enclosing reactive root) until
  the swap lands. A trigger may add `data-pjx-loading-extra="<css-selector>"` to also flag
  regions a bulk action will touch (e.g. rows a clear-completed removes). Style via `--pjx-*`
  CSS vars (`--pjx-skeleton-color`, `--pjx-spinner-color`, …).
- Every `load()` is memoized in `LoadCache` (one entry per `(type, key)`). Default scope is
  `CacheScope.REQUEST` (per-request, no cross-worker concern). Use
  `LoadCache.set_scope(CacheScope.PROCESS)` (or `setup(cache_scope=...)`) for process-wide
  caching, plus an `InvalidationBackend` (e.g. Redis) to fan out evictions across workers.

Full guide: [docs/reactivity.md](../reactivity.md).

## Builtins (`pyjinhx.builtins`)

Optional package: `import pyjinhx.builtins` then `from pyjinhx.builtins import Alert, Avatar, Badge, …` (twenty classes). Same `BaseComponent` rules; templates/CSS/JS live under `pyjinhx/builtins/ui/<component>/`. If the app Jinja loader does not see package templates, the **renderer falls back** to on-disk templates next to those classes.

**Do not** register user subclasses with the same **class name** as a builtin (`Card`, `Modal`, `Panel`, …) — global `Registry` is one class per name.

**Host theme (set on `:root` or a wrapper):** Builtin CSS reads shared tokens. Define at least: `--surface`, `--surface-alt`, `--text`, `--text-muted`, `--border`, `--brand`, `--brand-subtle`, `--brand-muted`, `--error`, `--success`, `--warning`, `--font-size-xs`, `--font-size-sm`, `--font-size-md`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-full`, `--shadow-md`, `--transition`, `--space-3`, `--space-4`. Optional but used for error surfaces: `--error-bg`, `--error-border` (badge/alert error variants fall back with `color-mix` if these are missing).

**Per-component tokens:** Each builtin stylesheet declares `--px-<widget>-*` custom properties on `:root` — override them to tune one component without editing package files (e.g. `--px-modal-width`, `--px-dropdown-z`, `--px-drawer-width`).

**Class naming:** BEM-style `px-<widget>`, `px-<widget>__element`, `px-<widget>--modifier`. A **`class_name` field** (appended on the root node) exists on `Avatar`, `Badge`, `Divider`, `Skeleton`.

**PascalCase tag quirks:** `TabGroup.tabs`, `Panel.panels`, `Breadcrumb.items` accept a **JSON string** attribute when rendered from tag strings (same idea as dict/list in Python). `Panel` / `PanelTrigger` **panel keys** must match `[a-zA-Z0-9_-]+` (stable `id`s). Components with bundled JS expose global helpers (e.g. `openModal(id)` / `closeModal(id)`, `openPxDrawer(id)`, `togglePxDropdown(id)`, `showNotification(id)`); others (`Popover`, `Panel`, `TabGroup`, `Tooltip`) use delegated events.

| Component | Purpose |
|-----------|---------|
| `Alert` | Inline dismissible message (info / success / warning / error) |
| `Avatar` | User image or initials, sized sm / md / lg |
| `Badge` | Small colored label / status pill |
| `Breadcrumb` | Navigation trail of `(label, href)` pairs |
| `Card` | Container with optional header / body / footer slots |
| `Divider` | Horizontal or vertical separator, optional label |
| `Drawer` | Slide-in `<dialog>` panel (left / right / bottom) |
| `Dropdown` | Toggleable trigger + menu |
| `EmptyState` | Placeholder for empty content with optional action |
| `LoadingOverlay` | Full-area spinner overlay |
| `Modal` | Centered `<dialog>` with backdrop |
| `Notification` | Corner-anchored auto-hiding toast |
| `Popover` | Hover/focus floating card (follow or anchor) |
| `Progress` | Determinate or indeterminate progress bar |
| `Panel` | Keyed content panels (paired with `PanelTrigger`) |
| `PanelTrigger` | Trigger that activates a `Panel` panel by key |
| `Skeleton` | Loading placeholder (text / circle / rect) |
| `Spinner` | Standalone loading spinner, sized sm / md / lg |
| `TabGroup` | Tabbed panels keyed by label |
| `Tooltip` | Hover/focus tip (top / bottom / start / end) |

Full reference (props, classes, `--px-*` tokens, JS helpers per component): [../guide/builtins.md](../guide/builtins.md).

## Registry

Components auto-register on definition (classes) and instantiation (instances). Composite key: `ClassName_id` — different types can share an ID.

For web apps, isolate per-request with `Registry.request_scope()`:

```python
from pyjinhx import Registry

with Registry.request_scope():
    btn = Button(id="submit", text="Go")
    html = btn.render()
# Cleaned up automatically
```

Or use middleware for app-wide coverage:

```python
class RegistryScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        with Registry.request_scope():
            return await call_next(request)
```

## Configuration

```python
from pyjinhx import Renderer

# Set template root (string path or Jinja2 Environment)
Renderer.set_default_environment("./components")

# Or use a custom Jinja2 Environment
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("./components"))
Renderer.set_default_environment(env)
```

## Project Structure

```
my_app/
├── components/
│   └── ui/
│       ├── button.py
│       ├── button.html
│       ├── button.js          # Optional, auto-collected
│       ├── button.css         # Optional, auto-collected
│       ├── card.py
│       └── card.html
├── main.py
└── pyproject.toml
```

## Public API

```python
from pyjinhx import (
    BaseComponent, ReactiveComponent, Renderer, Registry, Finder, Parser, Tag,
    PjxLoad, mutates, LoadCache, oob_swaps, client_script,
    PJX_MOUNTED_HEADER, PJX_TRIGGER_HEADER, setup,
)
import pyjinhx.builtins  # optional: registers all builtin classes
from pyjinhx.builtins import Alert, Modal, Panel, PanelTrigger, TabGroup  # …
```

- `BaseComponent` — base class for all components
- `ReactiveComponent` — dependency-aware components (`reacts_to` + `load()`); `Cls.render(*args)` is the route entry point
- `PjxLoad` — `Annotated[..., PjxLoad()]` marker for keyed `data-pjx-load` / manifest `load`
- `mutates` — decorator on store methods; state keys only (`@mutates("todos")`)
- `setup` — wires FastAPI middleware (`Registry.request_scope`, `ClientBackend`, `LoadContext`)
- `Renderer` — renders strings with PascalCase tags or manages environments
- `Registry` — query/clear instances and classes, `request_scope()` context manager
- `Finder` — template/asset discovery, `collect_javascript_files()`, `collect_css_files()`, `detect_root_directory()`
- `Parser` / `Tag` — HTML parsing internals (rarely needed directly)
- `LoadCache.invalidate` / `oob_swaps` — advanced: manual cache eviction and OOB walk
- `client_script` / `PJX_*_HEADER` — client runtime and wire-format header names
- `pyjinhx.builtins` — twenty optional UI components (see Builtins table above)
````

## Usage

After creating the file, use the `/pyjinhx` command in Claude Code before asking it to build components. Claude will then follow PyJinHx conventions automatically — correct file placement, naming, nesting patterns, and rendering approach.
