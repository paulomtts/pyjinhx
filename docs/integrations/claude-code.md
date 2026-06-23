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

A component is a Pydantic class plus a Jinja2 template in the **same directory**. `id` is optional — omitted/falsy ids auto-generate `pjx-<n>`; pass explicit ids for stable CSS/htmx targets. Reactive components need stable ids (defaulted to the kebab-cased class name; pass explicit ids for instance-keyed rows). Extra fields passed at instantiation are accepted unvalidated and available in the template context.

```python
from pyjinhx import BaseComponent

class Card(BaseComponent):
    id: str
    title: str
    subtitle: str = ""   # optional
```

The template is auto-discovered from the class name: `Card` → `card.pjx`/`card.html`/`card.jinja`; `ActionButton` → `action_button` or `action-button` (`.pjx`, `.html`, or `.jinja`, tried in that order — `.pjx` wins). Subclasses with no adjacent template inherit the nearest ancestor's template and assets through the MRO (first found per kind), so do **not** duplicate templates for every subclass; a class may have at most one concrete component base (definition-time `TypeError`).

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

## Escaping & slots (security)

Template output is **HTML-escaped by default** (Jinja runs with `autoescape=True`). Scalar props, text, attribute values, and loop-derived values are escaped — so user-supplied data can't inject markup. This is the secure default; do **not** defeat it for untrusted content.

What renders **raw** (unescaped):

- The component's children/`content` field (tag inner content).
- Any field declared `Slot` (`from pyjinhx import Slot`) — `Slot` is `str | BaseComponent`; its string value renders raw. `Slot` collections work too (string elements inside a `Slot`-annotated `list`/`dict`).
- Nested `BaseComponent` values (they render raw via `__html__`).

To intentionally render raw HTML / an icon / a snippet, opt in: declare the field as `Slot` (`badge: Slot = ""`), use `{{ value|safe }}` in the template, or pass a `BaseComponent`.

**Type matches escaping (convention).** A field's annotation must reflect how it renders. Text fields (titles, labels, descriptions) are plain `str` and stay escaped; raw-HTML/icon/component fields are `Slot`. **Never** type a text field `str | BaseComponent` unless it's a real slot — otherwise a component renders raw while a string escapes (inconsistent, and an XSS footgun).

```python
from pyjinhx import BaseComponent, Slot

class Callout(BaseComponent):
    title: str = ""      # text → escaped (safe default)
    body: Slot = ""      # raw HTML / icon / nested component → rendered as-is
```

## Nesting

Fields typed as components — `action: Button`, `items: list[Button]`, `widgets: dict[str, Button]` — are wrapped in `NestedComponentWrapper`: render with `{{ action }}`, read props via `{{ action.props.text }}`, loop lists/dicts normally. Lists and dicts may mix components with strings; nesting depth is unlimited.

## Assets (JS & CSS)

**Kebab-case** `.js`/`.css` files next to the component (`PJXTabGroup` → `pjx-tab-group.js`; a snake_case stem like `pjx_tab_group.js` is **not** collected) are auto-collected, deduplicated per render session, and injected at the root render — CSS as `<style>` before the HTML, JS as `<script>` after, one tag per component so an error in one doesn't break others. Subclasses with no adjacent assets inherit the nearest ancestor's assets through the MRO (first found per kind).

Add extra files via the `js=[...]` / `css=[...]` fields; missing files warn on the `pyjinhx` logger. For production, use `AssetMode.NONE` and serve assets from a pre-built bundle via `Finder.all_assets()`; see [One-bundle deployment](../guide/assets.md#one-bundle-deployment). For layout preload use `Finder(root).collect_javascript_files()` / `.collect_css_files()` or `layout_asset_tags()`.

## Reactivity (dependency-aware OOB swaps)

Server-side **cache invalidation, not signals** — no client watchers. Components declare state dependencies once; a mutation route re-emits exactly the mounted regions that depend on what changed, as HTMX out-of-band swaps.

Subclass `ReactiveComponent` and declare **both** the `react` class keyword and a `load()` classmethod (enforced: missing `load()` can't instantiate; missing `react` is a definition-time error):

```python
from typing import Annotated
from pyjinhx import MutationKey, PjxKey, ReactiveComponent, mutates

class Keys(MutationKey):
    TODOS = "todos"

class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())     # id defaults to "counter"
```

- `react` — `MutationKey` members *you* define. The server intersects them with pending `@mutates` keys to decide what to swap (and what to evict from the `load()` cache). Both `react=` and `@mutates` only accept `MutationKey` members; bare strings raise `TypeError`.
- `load()` — rebuilds the component from the current world, independent of any route.
- `id` defaults to the kebab-cased class name; pass an explicit `id` for instance-keyed regions (`id=f"row-{todo_id}"`).
- `state_hash()` gates swaps: a region is re-sent only if its fresh hash differs from the one the client reported.
- Roots are auto-stamped with `data-pjx-id` / `data-pjx-type` / `data-pjx-hash` / `data-pjx-reacts` (space-joined `react` keys, read by `pjx.js` to scope loading indicators) — plus `data-pjx-load` when keyed. A reactive component **must render a single root element**.

### Mutation routes return `render()` — nothing else

A mutation route does exactly one thing: `return <component>.render(...)`. Never call `load()` or assemble swaps yourself. Decorate store methods with `@mutates` using **`MutationKey` members only**:

```python
@mutates(Keys.TODOS)
def toggle_all():
    ...

@app.post("/todos/toggle")
def toggle():
    store.toggle_all()
    return Counter.render()
```

- **Class form (route entry)** — `Cls.render(*args)`: auto-`load()`s the primary, renders it as the HTMX main-target response, then appends OOB swaps for every *other* mounted reactive region whose `react` keys intersect the pending `@mutates` keys. **Only the primary is excluded** from OOB; the trigger region is not — a clicked region that depends on the dirtied keys updates itself OOB like any other dependent (e.g. a "Clear completed (N)" button refreshing its own count). `X-PJX-Trigger` is client-only (loading indicators); the server OOB walk reads the mounted manifest, never the trigger header.
- **Instance form** — `instance.render()`: plain render of an already-built instance, no re-`load()`.

Wire `setup(app, ...)` so `ClientBackend` is active — mutation routes need no `mounted`/`client` kwargs. `pjx.js` sends `X-PJX-Mounted`, `X-PJX-Assets`, and `X-PJX-Trigger` on every HTMX request. `oob_swaps(dirtied, mounted)` is exported for tests/advanced use.

### Instance-keyed regions (rows)

A component is keyed **iff `load()` takes one argument after `cls`**. Declare exactly one `Annotated[..., PjxKey()]` field — its value is stamped as `data-pjx-load` and returned in the manifest as `load` for OOB reloads.

```python
class TodoItemRow(ReactiveComponent, react={Keys.TODOS}):
    todo_id: Annotated[int, PjxKey()]
    title: str = ""

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

- Root full-page renders auto-inject `pjx.js` unless the request already carries `X-PJX-Mounted`. For a raw Jinja shell, call `client_script()` Python-side and pass it into the template context (e.g. `{"pjx_runtime": client_script()}`), then render with `{{ pjx_runtime }}` in `<head>` or `<body>`.
- **Loading indicators:** `data-pjx-loading="skeleton"` (or `"spinner"`) on any element inside a reactive root template flags it (matched via the enclosing reactive root) while an in-flight request dirties keys the region reacts to, until the swap lands. A trigger may add `data-pjx-loading-extra="<css-selector>"` to also flag regions a bulk action will touch. Style via `--pjx-*` CSS vars (`--pjx-skeleton-color`, `--pjx-spinner-color`, …).
- Every `load()` is memoized in `LoadCache`, one entry per `(type, key)`. Scope follows the backend: per-request with no `invalidation_backend`; pass `setup(invalidation_backend=...)` (e.g. Redis) for process-wide caching plus eviction fan-out across workers.

Full guide: [docs/reactivity.md](../reactivity.md).

## Builtins (`pyjinhx.builtins`)

`import pyjinhx.builtins` registers its optional components (`import pyjinhx.builtins as b; b.__all__` is the source of truth) — `PJXAccordion`, `PJXAlert`, `PJXButton`, `PJXCard`, `PJXDrawer`, `PJXDropdown`, `PJXLazyLoad`, `PJXModal`, `PJXPaginator`, `PJXPopover`, `PJXTable`, `PJXTabGroup`, and the rest. Same `BaseComponent` rules; templates/CSS/JS live under `pyjinhx/builtins/ui/pjx_<component>/`, and the renderer falls back to on-disk templates if the app's Jinja loader can't see package templates. **Do not** register user subclasses with the same class name as a builtin — the global `Registry` is one class per name.

- **Host theme** (set on `:root` or a wrapper): builtin CSS reads shared tokens — define at least `--surface`, `--surface-alt`, `--text`, `--text-muted`, `--border`, `--brand`, `--brand-subtle`, `--brand-muted`, `--error`, `--success`, `--warning`, `--font-size-{xs,sm,md}`, `--radius-{sm,md,lg,full}`, `--shadow-md`, `--transition`, `--space-3`, `--space-4`. Optional `--error-bg` / `--error-border` for error surfaces (badge/alert fall back with `color-mix`).
- **Per-component tokens:** each stylesheet declares `--pjx-<widget>-*` properties on `:root` — override to tune one component without editing package files (e.g. `--pjx-modal-width`, `--pjx-dropdown-z`, `--pjx-drawer-width`).
- **Classes** are BEM: `pjx-<widget>`, `pjx-<widget>__element`, `pjx-<widget>--modifier`. Every builtin accepts `class_name` (appended on the root) and `extra_attrs` (validated dict rendered on the root).
- **PascalCase tag quirks:** `PJXBreadcrumb.items` accepts a JSON-string attribute in tag strings (the dict/list equivalent). JS components use `window.pjx.*` APIs (`pjx.modal.open/close`, `pjx.drawer.open/close`, `pjx.popover.open/close/toggle`, `pjx.notification.show/hide`, `pjx.loader.region.show/hide/reset/wrap`, `pjx.confirm`, `pjx.prompt`, `pjx.toast`, `pjx.loader.page.*`); `PJXTabGroup`, `PJXTooltip` use delegated events with no exported API.

Full reference (props, classes, `--pjx-*` tokens, JS helpers per component): [Components](../components.md).

## Registry & configuration

Components auto-register on definition (classes) and instantiation (instances) under the composite key `ClassName_id`, so different types can share an ID. In web apps isolate per request with `with Registry.request_scope(): ...` — `setup(app)` already wires this as middleware, or wrap requests yourself.

Set the template root with `Renderer.set_default_environment(...)` — accepts a path string (`"./components"`) or a `jinja2.Environment`.

Keep each component's `.py`, template, and optional assets together, e.g. `components/ui/button.{py,html,js,css}`.

## Public API

```python
from pyjinhx import (
    BaseComponent,      # base class for all components
    ReactiveComponent,  # react={...} + load(); Cls.render(*args) is the route entry point
    Renderer, Registry,
    Slot,               # field type for raw-HTML/icon/component values (opt out of escaping)
    PjxKey,             # Annotated[..., PjxKey()] marker for keyed regions
    mutates,            # decorator on store methods; state keys only
    setup,              # wires FastAPI middleware (request_scope, ClientBackend, PjxContext)
)
# advanced/internal building blocks live in submodules:
from pyjinhx.finder import Finder        # asset/template discovery
from pyjinhx.utils import detect_root_directory  # locate project root
from pyjinhx.tags import Parser, Tag     # HTML parsing internals (rarely needed)
from pyjinhx.cache import LoadCache      # LoadCache.invalidate — manual cache eviction
from pyjinhx.reactive import oob_swaps   # manual OOB walk (tests/advanced)
from pyjinhx.client import PJX_MOUNTED_HEADER, PJX_TRIGGER_HEADER, client_script
import pyjinhx.builtins                  # optional: registers all builtin classes
```
````

## Usage

After creating the file, use the `/pyjinhx` command in Claude Code before asking it to build components. Claude will then follow PyJinHx conventions automatically — correct file placement, naming, nesting patterns, and rendering approach.
