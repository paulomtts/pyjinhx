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

Missing extra files emit a warning (check `pyjinhx` logger). For production, use `AssetMode.REFERENCE` with `Renderer.set_asset_url_resolver()`. Disable assets with `AssetMode.NONE` or legacy `Renderer.set_default_inline_js(False)` / `Renderer.set_default_inline_css(False)`. Use `Finder(root).collect_javascript_files()` / `Finder(root).collect_css_files()` or `layout_asset_tags()` for layout preload.

**Kebab vs snake for co-located assets:** `pascal_case_to_kebab_case(ClassName) + ".js"|".css"` (e.g. `TabGroup` → `tab-group.js`, `LoadingOverlay` → `loading-overlay.js`). Wrong stem (e.g. `tab_group.js`) is **not** collected.

## Reactivity (dependency-aware OOB swaps)

Declare each component's state dependencies once; a mutation route re-emits exactly the
mounted regions that depend on what changed (HTMX out-of-band swaps). "Reactivity" here
is **cache invalidation, not signals** — server-side, no client watchers.

Subclass `ReactiveComponent` and declare **both** `reacts_to` and a `load()` classmethod
(both enforced — missing `load()` can't instantiate; missing `reacts_to` is a
definition-time error):

```python
from typing import ClassVar
from pyjinhx import ReactiveComponent

class Counter(ReactiveComponent):
    remaining: int
    reacts_to: ClassVar[set[str]] = {"todos"}   # state keys you name (not ids/types)

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())     # id defaults to "counter"
```

- **`reacts_to`** — arbitrary state-key strings *you* choose (`"todos"`, `"user:42"`). The
  server intersects a component's `reacts_to` with a route's `dirtied` keys to decide what
  to swap (and what to evict from the `load()` cache).
- **`load()`** — rebuilds the component from the current world, independent of any route.
- **`id`** auto-defaults to the **kebab-cased class name** (`TodoCounter` → `"todo-counter"`);
  a singleton's identity is its type, so `load()` need not set one.
- `state_hash()` (hash of `model_dump_json()`) gates swaps: a region is re-sent only if its
  fresh hash differs from the one the client reported. Override only for custom hashing.
- Roots are auto-stamped with `data-pjx-id` / `data-pjx-type` / `data-pjx-hash` (+ `data-pjx-key`
  when keyed). A reactive component **must render a single root element**.

### Mutation routes return `render()` — nothing else

A mutation route does exactly one thing: **`return <component>.render(...)`**. You never
call `load()` and never assemble swaps yourself.

```python
@app.post("/todos/toggle")
def toggle(request):
    db.toggle_all()
    return Counter.render(dirtied={"todos"}, mounted=request)
```

`render` has two forms (one name):

- **Class form (reactive primary)** — `Cls.render(key=None, *, dirtied=None, mounted=None)`:
  auto-`load()`s the primary (by `key` if instance-keyed, zero-arg for a singleton), renders
  it as the main-target response, then appends an OOB swap for every *other* mounted reactive
  region whose `reacts_to` intersects `dirtied` (each rebuilt via its own `load()`). The
  primary's own region is never double-swapped. `dirtied` defaults to the primary's
  (interpolated) `reacts_to`.
- **Instance form (plain/constructed primary)** — `instance.render(*, dirtied=None, mounted=None)`:
  a non-reactive primary has no `load()`, so build it and render the instance.

`mounted` accepts a request-like object (the `X-PJX-Mounted` header is duck-typed off it — no
web-framework import), the raw header string, a parsed list, or `None`. With neither `dirtied`
nor `mounted`, `render()` is an ordinary plain render.

`oob_swaps(dirtied, mounted)` is what `render()` delegates to (`exclude_ids={primary.id}`);
it's exported for tests/advanced use but is **not** how you write a route.

### Instance-keyed regions (rows)

A reactive type can have **many independently-reactive instances** (table rows, cards). A
component is **instance-keyed iff its `load()` takes a parameter after `cls`** —
`load(cls, key)`; zero-arg `load(cls)` stays a type-singleton. No extra field or flag.

```python
class TodoItemRow(ReactiveComponent):
    title: str = ""
    reacts_to: ClassVar[set[str]] = {"todo"}          # instance-tier stem

    @classmethod
    def load(cls, key) -> "TodoItemRow":              # param after cls ⇒ keyed
        t = store.get(int(key))                        # keys arrive as str; coerce if typed
        return cls(title=t.text)

@app.post("/rows/{todo_id}/toggle")
def toggle_row(request, todo_id):
    store.toggle(todo_id)
    return TodoItemRow.render(todo_id, dirtied={f"todo:{todo_id}", "todos"}, mounted=request)
```

- **The key flows `render(key, …)` → `load(key)` automatically.** It derives the keyed id
  `f"{kebab(class)}-{key}"` (e.g. `todo-item-row-42`), is exposed to the template as `{{ key }}`,
  and is stamped as `data-pjx-key` so the manifest carries it back. Enums are unwrapped to
  `.value` before `load()`; cache/manifest keys are always `str`.
- **Instance-tier stems** on keyed components are bare strings (`{"todo"}` → `"todo:42"` per row).
  Collection-tier keys stay literal (`{"user", "users"}` — `"users"` is not suffixed).
- **Two-tier dirtying:** instance stems are *instance-tier* (`"todo:42"` swaps just that row);
  collection keys are *collection-tier* (`"todos"` swaps every mounted row that declares it, plus
  counters/totals). Name both as needed.

### Client runtime & cache

- A page shell marked **`base_layout=True`** auto-injects the client runtime (`pjx.js`), which
  emits the `X-PJX-Mounted` manifest on every htmx request:
  `class Page(BaseComponent, base_layout=True): ...`. For a raw Jinja shell, drop
  `{{ client_script() }}` in the `<head>` instead.
- Every `load()` is wrapped in a **process-global, dependency-keyed cache** (one entry per
  `(type, key)`), returning an independent copy each call. `render()`/`oob_swaps` evict the
  `dirtied` keys before reloading dependents, so swaps reflect post-mutation state. For
  mutations outside a render (jobs, webhooks) call `invalidate({"todos"})` yourself. Scope is
  per-process — back it with a shared store for multi-worker coherence.

Full guide: [docs/reactivity.md](../reactivity.md).

## Builtins (`pyjinhx.builtins`)

Optional package: `import pyjinhx.builtins` then `from pyjinhx.builtins import Alert, Avatar, Badge, …` (twenty classes). Same `BaseComponent` rules; templates/CSS/JS live under `pyjinhx/builtins/ui/<component>/`. If the app Jinja loader does not see package templates, the **renderer falls back** to on-disk templates next to those classes.

**Do not** register user subclasses with the same **class name** as a builtin (`Card`, `Modal`, `Panel`, …) — global `Registry` is one class per name.

**Host theme (set on `:root` or a wrapper):** Builtin CSS reads shared tokens. Define at least: `--surface`, `--surface-alt`, `--text`, `--text-muted`, `--border`, `--brand`, `--brand-subtle`, `--brand-muted`, `--error`, `--success`, `--warning`, `--font-size-xs`, `--font-size-sm`, `--font-size-md`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-full`, `--shadow-md`, `--transition`, `--space-3`, `--space-4`. Optional but used for error surfaces: `--error-bg`, `--error-border` (badge/alert error variants fall back with `color-mix` if these are missing).

**Per-component tokens:** Each builtin stylesheet declares `--px-<widget>-*` on `:root`. Override them to tune one component without editing package files (examples: `--px-modal-width`, `--px-dropdown-z`, `--px-drawer-width`).

**Class naming:** BEM-style `px-<widget>`, `px-<widget>__element`, `px-<widget>--modifier`. **`class_name` field** (appended on the root node): `Avatar`, `Badge`, `Divider`, `Skeleton`.

**PascalCase tag quirks:** `TabGroup.tabs`, `Panel.panels`, `Breadcrumb.items` accept a **JSON string** attribute when rendered from tag strings (same idea as dict/list in Python). `Panel` / `PanelTrigger` **panel keys** must match `[a-zA-Z0-9_-]+` (stable `id`s).

### Alert

- **Props:** `variant` info | success | warning | error; `title`, `body`, `dismissible`.
- **Classes:** `px-alert`, `px-alert__inner`, `px-alert__text`, `px-alert__title`, `px-alert__body`, `px-alert__dismiss`, `px-alert--info|success|warning|error`, `px-alert--dismissed`.
- **Tokens:** `--px-alert-radius`, `--px-alert-padding`, `--px-alert-border`, `--px-alert-shadow`, `--px-alert-title-size`, `--px-alert-body-size`, `--px-alert-dismiss-color` (variants also use `--brand`, `--success`, `--warning`, `--error`, and optionally `--error-bg` / `--error-border` for error).
- **JS:** `dismissPxAlert(id)`.

### Avatar

- **Props:** `src`, `alt`, `initials` (max 2 chars), `size` sm | md | lg, `class_name`.
- **Classes:** `px-avatar`, `px-avatar--sm|md|lg`, `px-avatar__img`, `px-avatar__initials`.
- **Tokens:** `--px-avatar-sm`, `--px-avatar-md`, `--px-avatar-lg`, `--px-avatar-bg`, `--px-avatar-fg`, `--px-avatar-border`, `--px-avatar-font-size-sm|md|lg`.

### Badge

- **Props:** `label`, `color` brand | error | neutral | muted, `shape` square | sm | md | full, `class_name`.
- **Classes:** `px-badge`, `px-badge--brand|error|neutral|muted`, `px-badge--square|sm|md|full`.
- **Tokens:** `--px-badge-font-size`, `--px-badge-radius-sm|md|full`, `--px-badge-brand-bg|fg|accent`, `--px-badge-error-bg|fg|border`, `--px-badge-neutral-bg|fg|border`, `--px-badge-muted-bg|fg|border`.

### Breadcrumb

- **Props:** `items` as `(label, href)` pairs (dict / JSON string in tags).
- **Classes:** `px-breadcrumb` (on `<nav>`), `px-breadcrumb__list`, `px-breadcrumb__item`, `px-breadcrumb__link`, `px-breadcrumb__current`.
- **Tokens:** `--px-breadcrumb-gap`, `--px-breadcrumb-sep` (e.g. `"/"`), `--px-breadcrumb-sep-color`, `--px-breadcrumb-link-color`, `--px-breadcrumb-current-color`, `--px-breadcrumb-font-size`.

### Card

- **Props:** `title`, `header`, `body`, `footer` (strings or nested components).
- **Classes:** `px-card`, `px-card__header`, `px-card__title`, `px-card__body`, `px-card__footer`.
- **Tokens:** `--px-card-bg`, `--px-card-border`, `--px-card-radius`, `--px-card-shadow`, `--px-card-title-color`, `--px-card-padding`, `--px-card-header-sep`, `--px-card-footer-sep`, `--px-card-footer-bg`.

### Divider

- **Props:** `orientation` horizontal | vertical, `label`, `class_name`.
- **Classes:** `px-divider--horizontal`, `px-divider--vertical`, `px-divider--labeled`, `px-divider__line`, `px-divider__label`.
- **Tokens:** `--px-divider-color`, `--px-divider-thickness`, `--px-divider-gap`, `--px-divider-label-color`, `--px-divider-label-size`.

### Drawer

- **Props:** `side` left | right | bottom; `title`, `body`, `footer`.
- **Classes:** `<dialog class="px-drawer px-drawer--left|right|bottom">`, `px-drawer__box`, `px-drawer__header`, `px-drawer__title`, `px-drawer__close`, `px-drawer__body`, `px-drawer__footer`, `px-drawer--closing` (animation). Slide distance: `--px-drawer-slide-from` is set on left/right variants in CSS.
- **Tokens:** `--px-drawer-width`, `--px-drawer-height-bottom`, `--px-drawer-bg`, `--px-drawer-border`, `--px-drawer-shadow`, `--px-drawer-backdrop`, `--px-drawer-header-bg`, `--px-drawer-header-sep`, `--px-drawer-footer-bg`, `--px-drawer-footer-sep`, `--px-drawer-padding`, `--px-drawer-z`.
- **JS:** `openPxDrawer(id)`, `closePxDrawer(id)`; clicking the dialog backdrop closes.

### Dropdown

- **Props:** `trigger`, `menu` (strings or nested components).
- **Classes:** `px-dropdown`, `px-dropdown__trigger`, `px-dropdown__menu`, `px-dropdown__menu--open` (toggle with `[hidden]`).
- **Tokens:** `--px-dropdown-menu-bg`, `--px-dropdown-menu-border`, `--px-dropdown-menu-radius`, `--px-dropdown-menu-shadow`, `--px-dropdown-menu-padding`, `--px-dropdown-menu-min-w`, `--px-dropdown-menu-max-h`, `--px-dropdown-z`.
- **JS:** `togglePxDropdown(id)`, `closePxDropdown(id)`; outside click and Escape close.

### EmptyState

- **Props:** `title`, `description`, `action`.
- **Classes:** `px-empty-state`, `px-empty-state__title`, `px-empty-state__desc`, `px-empty-state__action`.
- **Tokens:** `--px-empty-state-padding`, `--px-empty-state-max-width`, `--px-empty-state-title-size|color`, `--px-empty-state-desc-size|color`, `--px-empty-state-gap`.

### LoadingOverlay

- **Classes:** `px-loading-overlay`, `px-loading-overlay--visible`, `px-loading-overlay--hiding`, `px-loading-overlay__spinner`.
- **Tokens:** `--px-loading-overlay-bg`, `--px-loading-overlay-backdrop`, `--px-loading-overlay-z`, `--px-loading-overlay-spinner-size`, `--px-loading-overlay-spinner-width`, `--px-loading-overlay-spinner-color`, `--px-loading-overlay-spinner-track`.
- **JS:** `showLoadingOverlay(id)`, `hideLoadingOverlay(id)`.

### Modal

- **Props:** `title`, `header` (replaces title when set), `body`, `footer`.
- **Classes:** `<dialog class="px-modal">`, `px-modal--closing`, `px-modal__box`, `px-modal__header`, `px-modal__title`, `px-modal__close`, `px-modal__body`, `px-modal__footer`; `::backdrop` uses `--px-modal-backdrop`.
- **Tokens:** `--px-modal-width`, `--px-modal-min-height`, `--px-modal-bg`, `--px-modal-border`, `--px-modal-radius`, `--px-modal-shadow`, `--px-modal-header-bg`, `--px-modal-header-sep`, `--px-modal-footer-bg`, `--px-modal-footer-sep`, `--px-modal-title-color`, `--px-modal-close-color`, `--px-modal-backdrop`, `--px-modal-padding`.
- **JS:** `openModal(id)`, `closeModal(id)`; clicking the bare `<dialog>` backdrop closes.

### Notification

- **Props:** `content`, `corner` top-right | top-left | bottom-right | bottom-left, `timeout` (ms, `0` = no auto-hide).
- **Classes:** `px-notification`, `px-notification--top-right|top-left|bottom-right|bottom-left`, `px-notification--visible`, `px-notification--hiding`, `px-notification__content`, `px-notification__close`.
- **Tokens:** `--px-notification-width`, `--px-notification-gap`, `--px-notification-bg`, `--px-notification-border`, `--px-notification-radius`, `--px-notification-shadow`, `--px-notification-padding`, `--px-notification-close-color`, `--px-notification-z`.
- **JS:** `showNotification(id)`, `hideNotification(id)`; reads `data-timeout`.

### Popover

- **Props:** `content`, `card_content`, `position` follow | anchor.
- **Classes:** `px-popover-trigger` (optional `data-popover-backdrop`), `px-popover-card`, `px-popover-card--visible`, `#px-popover-backdrop` / `px-popover-backdrop`, `px-popover-backdrop--visible`.
- **Tokens:** `--px-popover-max-width`, `--px-popover-bg`, `--px-popover-border`, `--px-popover-radius`, `--px-popover-shadow`, `--px-popover-padding`, `--px-popover-z`.
- **JS:** Delegated hover / focus / mousemove; single shared backdrop element.

### Progress

- **Props:** `value` (omit or `None` for indeterminate bar), `max`, `label`.
- **Classes:** `px-progress`, `px-progress__label`, `px-progress__bar` (`<progress>`; `indeterminate` styling when no value).
- **Tokens:** `--px-progress-height`, `--px-progress-radius`, `--px-progress-track`, `--px-progress-fill`, `--px-progress-indeterminate-speed`.

### Panel

- **Props:** `panels` map panel-key → content (dict or JSON string in tags).
- **Classes:** `px-panel`, `px-panel__panel` (`[hidden]` toggles visibility). Almost no layout tokens in package CSS—style the host layout around it.
- **JS:** With `PanelTrigger`: delegated `click` on `.px-panel-trigger`; `pxPanelInit()` on `DOMContentLoaded`, `htmx:afterSwap`, `htmx:afterSettle`; helpers `pxPanelShowPanel(hostRoot, panelKey)`, `pxPanelSyncTriggers(hostId, activeKey)`.

### PanelTrigger

- **Props:** `panel_id`, `panel` (key matching the parent `Panel.panels`), `content` (your visible markup inside the wrapper).
- **Classes:** `px-panel-trigger` (`display: contents`; delegated `click` in `panel.js` from `Panel`).

### Skeleton

- **Props:** `variant` text | circle | rect, `lines` (for text), `class_name`.
- **Classes:** `px-skeleton`, `px-skeleton--text|circle|rect`, `px-skeleton__line`, `px-skeleton__circle`, `px-skeleton__rect`.
- **Tokens:** `--px-skeleton-bg`, `--px-skeleton-shine`, `--px-skeleton-line-height`, `--px-skeleton-line-gap`, `--px-skeleton-circle-size`, `--px-skeleton-rect-height`, `--px-skeleton-rect-radius`, `--px-skeleton-duration`.

### Spinner

- **Props:** `size` sm | md | lg, `label`.
- **Classes:** `px-spinner`, `px-spinner--sm|md|lg`, `px-spinner__ring`, `px-spinner__label`.
- **Tokens:** `--px-spinner-sm|md|lg`, `--px-spinner-track`, `--px-spinner-accent`.

### TabGroup

- **Props:** `tabs` map label → panel content (dict or JSON string in tags).
- **Classes:** `px-tab-group`, `px-tab-group__list`, `px-tab-group__tab`, `px-tab-group__panel` (`[hidden]` on inactive panels; `aria-selected` on tabs).
- **Tokens:** `--px-tab-group-border`, `--px-tab-group-bg`, `--px-tab-group-tab-fg`, `--px-tab-group-tab-active-fg`, `--px-tab-group-tab-active-bg`, `--px-tab-group-tab-active-border`, `--px-tab-group-panel-bg`, `--px-tab-group-radius`, `--px-tab-group-padding`.
- **JS:** Delegated `click` on `.px-tab-group__tab` only.

### Tooltip

- **Props:** `trigger`, `tip`, `placement` top | bottom | start | end.
- **Classes:** `px-tooltip` with `data-px-tooltip-placement`, `px-tooltip__trigger`, `px-tooltip__tip`, `px-tooltip__tip--visible`.
- **Tokens:** `--px-tooltip-gap`, `--px-tooltip-bg`, `--px-tooltip-border`, `--px-tooltip-radius`, `--px-tooltip-shadow`, `--px-tooltip-padding`, `--px-tooltip-max-width`, `--px-tooltip-fg`, `--px-tooltip-font-size`, `--px-tooltip-z`.
- **JS:** Delegated focus / blur / mouse enter / leave; placement reads `--px-tooltip-gap` and `data-px-tooltip-placement`.

| Class | Bundled JS (globals unless noted) |
|-------|-----------------------------------|
| `Alert` | `dismissPxAlert(id)` |
| `Drawer` | `openPxDrawer(id)`, `closePxDrawer(id)` |
| `Dropdown` | `togglePxDropdown(id)`, `closePxDropdown(id)` |
| `LoadingOverlay` | `showLoadingOverlay(id)`, `hideLoadingOverlay(id)` |
| `Modal` | `openModal(id)`, `closeModal(id)` |
| `Notification` | `showNotification(id)`, `hideNotification(id)` |
| `Popover` | Delegated events + `#px-popover-backdrop` |
| `Panel` | `pxPanelInit()`, `pxPanelShowPanel`, `pxPanelSyncTriggers` (+ trigger clicks) |
| `TabGroup` | Delegated tab clicks |
| `Tooltip` | Delegated focus/hover + placement |

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
    oob_swaps, invalidate, client_script, PJX_MOUNTED_HEADER,
)
import pyjinhx.builtins  # optional: registers all builtin classes
from pyjinhx.builtins import Alert, Modal, Panel, PanelTrigger, TabGroup  # …
```

- `BaseComponent` — base class for all components
- `ReactiveComponent` — base class for dependency-aware reactive components (`reacts_to` + `load()`); `Cls.render(key=None, *, dirtied=, mounted=)` is the auto-loading route entry point
- `Renderer` — renders strings with PascalCase tags or manages environments
- `Registry` — query/clear instances and classes, `request_scope()` context manager
- `Finder` — template/asset discovery, `collect_javascript_files()`, `collect_css_files()`, `detect_root_directory()`
- `Parser` / `Tag` — HTML parsing internals (rarely needed directly)
- `oob_swaps` / `invalidate` — reactivity internals: the dependency walk and manual `load()`-cache eviction
- `client_script` / `PJX_MOUNTED_HEADER` — client-runtime `<script>` for raw shells; the mounted-manifest header name
- `pyjinhx.builtins` — twenty optional UI components (see Builtins table above)
````

## Usage

After creating the file, use the `/pyjinhx` command in Claude Code before asking it to build components. Claude will then follow PyJinHx conventions automatically — correct file placement, naming, nesting patterns, and rendering approach.
