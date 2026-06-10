# Claude Code

You can use the following skill as a [custom slash command](https://docs.anthropic.com/en/docs/claude-code/slash-commands) in Claude Code to help the AI build with PyJinHx.

## Setup

Create a file at `.claude/commands/pyjinhx.md` in your project root with the following content:

````markdown
---
name: pyjinhx
description: Build reusable, type-safe UI components with PyJinHx (Pydantic + Jinja2)
---

You are building with PyJinHx — reusable, type-safe UI components from Pydantic + Jinja2.

## Components

A component is a Pydantic class plus a Jinja2 template in the **same directory**. `id` is optional — omitted/falsy ids auto-generate `px-<n>`; pass explicit ids for stable CSS/htmx targets. Reactive components need stable ids (defaulted to the kebab-cased class name; pass explicit ids for instance-keyed rows). Extra fields passed at instantiation are accepted unvalidated and available in the template context.

```python
from pyjinhx import BaseComponent

class Card(BaseComponent):
    id: str
    title: str
    subtitle: str = ""   # optional
```

The template is auto-discovered from the class name: `Card` → `card.html`/`card.jinja`; `ActionButton` → `action_button` or `action-button` (`.html` or `.jinja`).

## Rendering

- **Python-side:** `Card(id="c1", title="Hi").render()`
- **String-side:** `Renderer.get_default_renderer().render('<Card id="c1" title="Hi"/>')`

PascalCase tags resolve in order: registered instance with matching id (reused, props updated) → registered class with matching name (new instance, Pydantic-validated) → generic fallback (BaseComponent + discovered template, no validation). Tag inner content becomes `{{ content }}`.

Templates receive all component fields as variables and support full Jinja2. PascalCase tags work inside **any** template — component, page, or string passed to `renderer.render()` — so components compose declaratively:

```html
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {% if subtitle %}<p>{{ subtitle }}</p>{% endif %}
    <Button id="card-action" text="Click me"/>
</div>
```

## Nesting

Fields typed as components — `action: Button`, `items: list[Button]`, `widgets: dict[str, Button]` — are wrapped in `NestedComponentWrapper`: render with `{{ action }}`, read props via `{{ action.props.text }}`, loop lists/dicts normally. Lists and dicts may mix components with strings; nesting depth is unlimited.

## Assets (JS & CSS)

**Kebab-case** `.js`/`.css` files next to the component (`TabGroup` → `tab-group.js`; a snake_case stem like `tab_group.js` is **not** collected) are auto-collected, deduplicated per render session, and injected at the root render — CSS as `<style>` before the HTML, JS as `<script>` after, one tag per component so an error in one doesn't break others.

Add extra files via the `js=[...]` / `css=[...]` fields; missing files warn on the `pyjinhx` logger. For production use `AssetMode.REFERENCE` with `Renderer.set_asset_url_resolver()`; disable with `AssetMode.NONE`. For layout preload use `Finder(root).collect_javascript_files()` / `.collect_css_files()` or `layout_asset_tags()`.

## Reactivity (dependency-aware OOB swaps)

Server-side **cache invalidation, not signals** — no client watchers. Components declare state dependencies once; a mutation route re-emits exactly the mounted regions that depend on what changed, as HTMX out-of-band swaps.

Subclass `ReactiveComponent` and declare **both** `reacts_to` and a `load()` classmethod (enforced: missing `load()` can't instantiate; missing `reacts_to` is a definition-time error):

```python
from typing import Annotated, ClassVar
from pyjinhx import PjxKey, ReactiveComponent, mutates

class Counter(ReactiveComponent):
    remaining: int
    reacts_to: ClassVar[set[str]] = {"todos"}   # state keys you name (not ids/types)

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())     # id defaults to "counter"
```

- `reacts_to` — arbitrary state-key strings *you* choose. The server intersects them with pending `@mutates` keys to decide what to swap (and what to evict from the `load()` cache).
- `load()` — rebuilds the component from the current world, independent of any route.
- `id` defaults to the kebab-cased class name; pass an explicit `id` for instance-keyed regions (`id=f"row-{todo_id}"`).
- `state_hash()` gates swaps: a region is re-sent only if its fresh hash differs from the one the client reported.
- Roots are auto-stamped with `data-pjx-id` / `data-pjx-type` / `data-pjx-hash` / `data-pjx-reacts` (space-joined `reacts_to`, read by `pjx.js` to scope loading indicators) — plus `data-pjx-load` when keyed. A reactive component **must render a single root element**.

### Mutation routes return `render()` — nothing else

A mutation route does exactly one thing: `return <component>.render(...)`. Never call `load()` or assemble swaps yourself. Decorate store methods with `@mutates` on **state keys only**:

```python
@mutates("todos")
def toggle_all():
    ...

@app.post("/todos/toggle")
def toggle():
    store.toggle_all()
    return Counter.render()
```

- **Class form (route entry)** — `Cls.render(*args)`: auto-`load()`s the primary, renders it as the HTMX main-target response, then appends OOB swaps for every *other* mounted reactive region whose `reacts_to` intersects the pending `@mutates` keys. **Only the primary is excluded** from OOB; the trigger region is not — a clicked region that depends on the dirtied keys updates itself OOB like any other dependent (e.g. a "Clear completed (N)" button refreshing its own count). `X-PJX-Trigger` is client-only (loading indicators); the server OOB walk reads the mounted manifest, never the trigger header.
- **Instance form** — `instance.render()`: plain render of an already-built instance, no re-`load()`.

Wire `setup(app, ...)` so `ClientBackend` is active — mutation routes need no `mounted`/`client` kwargs. `pjx.js` sends `X-PJX-Mounted`, `X-PJX-Assets`, and `X-PJX-Trigger` on every HTMX request. `oob_swaps(dirtied, mounted)` is exported for tests/advanced use.

### Instance-keyed regions (rows)

A component is keyed **iff `load()` takes one argument after `cls`**. Declare exactly one `Annotated[..., PjxKey()]` field — its value is stamped as `data-pjx-load` and returned in the manifest as `load` for OOB reloads.

```python
class TodoItemRow(ReactiveComponent):
    todo_id: Annotated[int, PjxKey()]
    title: str = ""
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls, todo_id: int | str) -> "TodoItemRow":
        t = store.get(int(todo_id))
        return cls(id=f"row-{t.id}", todo_id=t.id, title=t.text)

@app.post("/rows/{todo_id}/toggle")
def toggle_row(todo_id: int):
    store.toggle(todo_id)
    return TodoItemRow.render(todo_id)   # → load(todo_id) automatically
```

Set an explicit `id` in `load()` for stable DOM targets; templates use the key field (`hx-post="/rows/{{ todo_id }}/toggle"`). Hash-gating skips unchanged regions. If a keyed `load(manifest.load)` raises `LookupError` during the OOB walk, a `delete:[data-pjx-id='…']` swap removes the stale region (e.g. after clear-completed removes rows still in the manifest).

### Client runtime & cache

- Root full-page renders auto-inject `pjx.js` unless the request already carries `X-PJX-Mounted`. For a raw Jinja shell, put `{{ client_script() }}` in `<head>`.
- **Loading indicators:** `data-pjx-loading="skeleton"` (or `"spinner"`) on any element inside a reactive root template flags it (matched via the enclosing reactive root) while an in-flight request dirties keys the region `reacts_to`, until the swap lands. A trigger may add `data-pjx-loading-extra="<css-selector>"` to also flag regions a bulk action will touch. Style via `--pjx-*` CSS vars (`--pjx-skeleton-color`, `--pjx-spinner-color`, …).
- Every `load()` is memoized in `LoadCache`, one entry per `(type, key)`. Scope follows the backend: per-request with no `invalidation_backend`; pass `setup(invalidation_backend=...)` (e.g. Redis) for process-wide caching plus eviction fan-out across workers.

Full guide: [docs/reactivity.md](../reactivity.md).

## Builtins (`pyjinhx.builtins`)

`import pyjinhx.builtins` registers thirty-three optional components: `Alert`, `Avatar`, `AvatarStack`, `Badge`, `Breadcrumb`, `Card`, `ChipInput`, `ConfirmDialog`, `Divider`, `Drawer`, `Dropdown`, `EmptyState`, `FormField`, `LazyPanel`, `Modal`, `Notification`, `PageLoader`, `PasswordInput`, `Popover`, `PopoverPanel`, `PopoverTrigger`, `Progress`, `PromptDialog`, `RegionLoader`, `Panel`, `PanelTrigger`, `SegmentedControl`, `Skeleton`, `Spinner`, `TabGroup`, `ToastHost`, `ToggleSwitch`, `Tooltip`. Same `BaseComponent` rules; templates/CSS/JS live under `pyjinhx/builtins/ui/<component>/`, and the renderer falls back to on-disk templates if the app's Jinja loader can't see package templates. **Do not** register user subclasses with the same class name as a builtin — the global `Registry` is one class per name.

- **Host theme** (set on `:root` or a wrapper): builtin CSS reads shared tokens — define at least `--surface`, `--surface-alt`, `--text`, `--text-muted`, `--border`, `--brand`, `--brand-subtle`, `--brand-muted`, `--error`, `--success`, `--warning`, `--font-size-{xs,sm,md}`, `--radius-{sm,md,lg,full}`, `--shadow-md`, `--transition`, `--space-3`, `--space-4`. Optional `--error-bg` / `--error-border` for error surfaces (badge/alert fall back with `color-mix`).
- **Per-component tokens:** each stylesheet declares `--px-<widget>-*` properties on `:root` — override to tune one component without editing package files (e.g. `--px-modal-width`, `--px-dropdown-z`, `--px-drawer-width`).
- **Classes** are BEM: `px-<widget>`, `px-<widget>__element`, `px-<widget>--modifier`. Every builtin accepts `class_name` (appended on the root) and `extra_attrs` (validated dict rendered on the root).
- **PascalCase tag quirks:** `TabGroup.tabs`, `Panel.panels`, `Breadcrumb.items` accept a JSON-string attribute in tag strings (the dict/list equivalent). `Panel` / `PanelTrigger` panel keys must match `[a-zA-Z0-9_-]+` (stable `id`s). JS components use `window.px.*` APIs (`px.modal.open/close`, `px.drawer.open/close`, `px.popover.open/close/toggle`, `px.notification.show/hide`, `px.loader.region.show/hide/reset/wrap`, `px.confirm`, `px.prompt`, `px.toast`, `px.loader.page.*`); `Panel`, `TabGroup`, `Tooltip` use delegated events with no exported API.

Full reference (props, classes, `--px-*` tokens, JS helpers per component): [../guide/builtins.md](../guide/builtins.md).

## Registry & configuration

Components auto-register on definition (classes) and instantiation (instances) under the composite key `ClassName_id`, so different types can share an ID. In web apps isolate per request with `with Registry.request_scope(): ...` — `setup(app)` already wires this as middleware, or wrap requests yourself.

Set the template root with `Renderer.set_default_environment(...)` — accepts a path string (`"./components"`) or a `jinja2.Environment`.

Keep each component's `.py`, template, and optional assets together, e.g. `components/ui/button.{py,html,js,css}`.

## Public API

```python
from pyjinhx import (
    BaseComponent,      # base class for all components
    ReactiveComponent,  # reacts_to + load(); Cls.render(*args) is the route entry point
    Renderer, Registry,
    PjxKey,             # Annotated[..., PjxKey()] marker for keyed regions
    mutates,            # decorator on store methods; state keys only
    setup,              # wires FastAPI middleware (request_scope, ClientBackend, PjxContext)
)
# advanced/internal building blocks live in submodules:
from pyjinhx.finder import Finder        # asset/template discovery, detect_root_directory()
from pyjinhx.tags import Parser, Tag     # HTML parsing internals (rarely needed)
from pyjinhx.cache import LoadCache      # LoadCache.invalidate — manual cache eviction
from pyjinhx.reactive import oob_swaps   # manual OOB walk (tests/advanced)
from pyjinhx.client import PJX_MOUNTED_HEADER, PJX_TRIGGER_HEADER, client_script
import pyjinhx.builtins                  # optional: registers all builtin classes
```
````

## Usage

After creating the file, use the `/pyjinhx` command in Claude Code before asking it to build components. Claude will then follow PyJinHx conventions automatically — correct file placement, naming, nesting patterns, and rendering approach.
