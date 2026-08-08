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

A component is a Pydantic class plus a Jinja2 template in the **same directory**. `id` is optional — omitted/falsy ids auto-generate `pjx-<n>`. There is no class-name-derived default, so anything that has to be addressable (every reactive region, every htmx target) needs an explicit `id`. `BaseComponent` is strict (`model_config = ConfigDict(extra="forbid")`): an undeclared kwarg raises a validation error. For pass-through attributes, opt the class into pydantic's own `extra="allow"` — `class Card(BaseComponent): model_config = ConfigDict(extra="allow")`. There is no pyjinhx base class to import for this; classless and `{#def#}` components are generated with the same config.

```python
from pyjinhx import BaseComponent

class Card(BaseComponent):
    id: str
    title: str
    subtitle: str = ""   # optional
```

The template is auto-discovered from the class name, snake_cased, with a `.pjx` extension, in the class's own module directory: `Card` → `card.pjx`; `ActionButton` → `action_button.pjx`. That is the **only** shape probed — no `.html`, no `.jinja`, no kebab-case stems. Subclasses with no adjacent template inherit the nearest ancestor's template and assets through the MRO (first found per kind), so do **not** duplicate templates for every subclass. Inherit from **one** concrete component base: a second one does not raise, it is silently ignored — MRO resolution takes the first base's template.

## Rendering

- **Instance method:** `Card(id="c1", title="Hi").render()`
- **Free function:** `from pyjinhx import render; render(Card(id="c1", title="Hi"))`

Both return a final HTML string for **that one component's tree** — `render()` never appends OOB swaps and never reads the client's manifest. Fan-out belongs to the response composer (see [Mutation routes](#mutation-routes)).

PascalCase tags resolve against the process-wide tag → class registry, keyed by the snake_cased tag name (`<ActionButton/>` → `action_button`). A hit is built once per tag: a plain class through its Pydantic constructor (attrs validated), a reactive class through its cache-routed `load()` factory with the key attr passed in and the remaining attrs assigned after. A miss is not an error — the tag goes back into the stream as literal markup. (The *instance* registry is a separate, request-scoped structure used only by reactivity; tags never resolve through it.) Tag inner content becomes `{{ content }}`.

Templates receive all component fields as variables and support full Jinja2. PascalCase tags work inside **any** template — component, page, or nested component — so components compose declaratively:

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

`.js`/`.css` files next to the component sharing the template's **snake_case** stem (`PJXTabGroup` → `pjx_tab_group.pjx` + `pjx_tab_group.js`; a kebab-case `pjx-tab-group.js` is **not** collected) are auto-collected, deduplicated per render session, and injected at the root render — CSS as `<style>` before the HTML, JS as `<script>` after, one tag per component so an error in one doesn't break others. Subclasses with no adjacent assets inherit the nearest ancestor's assets through the MRO (first found per kind).

Add extra files via the `js=[...]` / `css=[...]` fields; missing files warn on the `pyjinhx` logger. For production, use `AssetMode.NONE` (from `pyjinhx`) and serve assets from a pre-built bundle via `pyjinhx.assets.all_assets()` (internal module, not public API), which walks every registered component class and returns its `(css_paths, js_paths)`.

## Reactivity (dependency-aware OOB swaps)

Server-side **cache invalidation, not signals** — no client watchers. Components declare state dependencies once; the response composer re-emits exactly the mounted regions that depend on what changed, as HTMX out-of-band swaps.

Subclass `ReactiveComponent` and declare **both** the `react` class keyword and a `load()` **classmethod**. `load()` must be a classmethod returning an instance — an instance-method `load(self)` raises at class-definition time. Neither is strictly required (a class with no `react` simply reacts to nothing; the inherited `load()` returns a field-default instance), but a useful reactive component declares both:

```python
from typing import Annotated
from pyjinhx import MutationKey, PjxKey, ReactiveComponent, mutates

class Keys(MutationKey):
    TODOS = "todos"

class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())
```

Mount it with an explicit id — from the tag (`<Counter id="counter"/>`), or set in `load()` for keyed rows.

- `react` — `MutationKey` members *you* define. The server intersects them with pending `@mutates` keys to decide what to swap (and what to evict from the `load()` cache). `@mutates(...)` and `dirty(...)` accept `MutationKey` members and `reactive_key()` values only — a bare string raises `TypeError`. `react=` normalizes whatever it is given to the member's string value, so declare it with the same `MutationKey` members and the two sides can't drift.
- `load()` — rebuilds the component from the current world, independent of any route.
- `id` has no class-name default (`pjx-<n>` otherwise), so always give a reactive region a stable one: from the mounting tag, or set in `load()` for instance-keyed regions (`id=f"row-{todo_id}"`).
- `state_hash()` gates swaps: a region is re-sent only if its fresh hash differs from the one the client reported.
- Roots are auto-stamped with `data-pjx-id`, `data-pjx-type` (the **snake_case tag name**, not the class name), `data-pjx-hash`, and `data-pjx-load` when the class has a `PjxKey` field. `data-pjx-reacts` is **not** stamped — `pjx.js` only reads it, so a template that wants the loading-indicator scoping must render it itself (`data-pjx-reacts="todos"` on the root). A reactive component **must render a single root element**.

### Mutation routes

A route **returns the component it wants swapped in place** and lets the response composer build the wire response. Dirtying happens *before* the return, via `@mutates` on store methods (`MutationKey` members only) or an imperative `dirty(...)`:

```python
from pyjinhx import dirty, mutates


@mutates(Keys.TODOS)
def toggle_all():
    ...


@app.post("/todos/toggle")
def toggle():
    store.toggle_all()          # @mutates dirties Keys.TODOS
    return Counter.load()       # primary; every dependent region fans out OOB


@app.post("/todos/dismiss")
def dismiss():
    store.dismiss()
    dirty(Keys.TODOS)           # plain mutation, no @mutates
    return None                 # no primary; dependents still fan out OOB
```

`pyjinhx.responses.compose(result, *, session=None)` is what turns a handler return into a `PjxResponse(body, headers, status)`, and it attaches fan-out on **every** path that produces a body — the dirtied keys belong to the request, not to whichever spelling the handler reached for. Four return shapes:

| Return | Primary |
| --- | --- |
| a `BaseComponent` | rendered as the primary |
| `None` | empty primary, plus `HX-Reswap: none` so htmx leaves the trigger alone |
| `str` / `Markup` / any `__html__` object | used verbatim |
| anything else | `PASSTHROUGH` — the backend keeps its own value untouched |

`render()` itself is an **instance method** (`BaseComponent.render(self, session=None)`) that returns one component's markup and nothing else. There is no `Cls.render(*args)` classmethod, and calling `.render()` in a handler opts that response out of nothing — but returning the component is the normal form.

The body is the primary followed by one OOB fragment per mounted reactive region whose `react` keys intersect this request's dirtied keys. **Every `data-pjx-id` the serialized primary already carries is excluded** from the OOB legs, so no region is swapped twice; the trigger region is otherwise not special — a clicked region that depends on the dirtied keys updates itself OOB like any other dependent (e.g. a "Clear completed (N)" button refreshing its own count). `X-PJX-Trigger` is client-only (loading indicators); the server OOB walk reads the mounted manifest, never the trigger header.

**Redirects.** There is no pyjinhx redirect helper and no setting: return your framework's own redirect (`RedirectResponse("/login")`). It leaves `compose()` as `PASSTHROUGH`, and the backend then translates any result with a 3xx status *and* a `Location` header into `204` + `HX-Redirect` for requests carrying `HX-Request`. Detection is duck-typed on that shape, not on a class. A non-htmx request gets the real 3xx untouched. `HX-Location` has no pyjinhx surface — spell it `Response(status_code=204, headers={"HX-Location": "/x"})`, which passes through untouched.

Wire `setup(app, ...)` so the framework adapter (e.g. FastAPI) installs `PjxScopeMiddleware` — it opens the request scope, parses `X-PJX-Mounted`/`X-PJX-Assets` onto the session, and subscribes asset accumulation, root stamping and instance registration, so routes need no extra kwargs. `pjx.js` sends `X-PJX-Mounted`, `X-PJX-Assets`, and `X-PJX-Trigger` on every HTMX request. `oob_swaps(candidates)` is exported for tests/advanced use. Full detail: [Response composition](../api/responses.md).

### Instance-keyed regions (rows)

Declare exactly one `Annotated[..., PjxKey()]` field — its value is stamped as `data-pjx-load` and reported back in the manifest as `load` for OOB reloads. `load()` then takes that field by name after `cls`.

```python
class TodoItemRow(ReactiveComponent, react={Keys.TODOS}):
    todo_id: Annotated[int, PjxKey()]
    title: str = ""

    @classmethod
    def load(cls, todo_id: int) -> "TodoItemRow":
        t = store.get(todo_id)          # KeyError here is the delete signal — do not catch it
        return cls(id=f"row-{t.id}", todo_id=t.id, title=t.text)

@app.post("/rows/{todo_id}/toggle")
def toggle_row(todo_id: int):
    store.toggle(todo_id)
    return TodoItemRow.load(todo_id)    # factory form: Cls.load(...) returns the instance
```

`data-pjx-load` round-trips through an HTML attribute as a string, but the framework validates it back to the `PjxKey` field's **declared type** before calling `load()` — a `todo_id: int` arrives as an `int`. Never coerce it yourself.

Set an explicit `id` in `load()` for stable DOM targets; templates use the key field (`hx-post="/rows/{{ todo_id }}/toggle"`). Hash-gating skips unchanged regions.

**Raising is part of `load()`'s contract.** A `LookupError` out of `load()` during the OOB walk is the *sole* signal that a region is gone, and it is what emits `<div hx-swap-oob="delete:[data-pjx-id='…']"></div>` (e.g. after clear-completed removes rows the client still shows). `KeyError` and `IndexError` subclass `LookupError`, so an ordinary dict/list lookup against your own store is already the right signal — let it out. A `load()` that catches its store's `KeyError` and returns a field-default instance gets its region swapped with a **blank render instead of deleted**. A miss in the request-scoped *instance registry* means nothing of the sort: out-of-primary regions miss it routinely.

### Client runtime & cache

- Root full-page renders auto-inject htmx + `pjx.js` unless the request already carries `X-PJX-Mounted` (inline JS mode only; `inject_runtime(session, request)` is the hook, called by the backend's `to_response()`). For a raw Jinja shell (outside the component render path), build the tags Python-side and pass them in as `Markup` — the readers return **bare JS source**, so an unwrapped `{{ pjx_runtime }}` would emit autoescaped script text into the page, and `pjx.js` needs htmx loaded first:

  ```python
  from markupsafe import Markup
  from pyjinhx.client import (  # internal module, not public API
      read_loading_indicator_js,
      read_page_loader_js,
      read_pjx_runtime,
      read_pjx_style_css,
      read_vendored_htmx,
  )

  pjx_runtime = Markup(
      f'<style id="pjx-style">{read_pjx_style_css()}</style>'
      f"<script>{read_vendored_htmx()}{read_pjx_runtime()}"
      f"{read_loading_indicator_js()}{read_page_loader_js()}</script>"
  )
  ```

  Then render `{{ pjx_runtime }}` in `<head>` (or use `{{ pjx_runtime|safe }}` if you pass a plain string). Same order as `inject_runtime`: vendored htmx (self-guarded, so a page with its own htmx keeps it), then `pjx.js`, then the loading artifacts, which call `pjx.region`/`pjx.loadingTargets`.
- **Loading indicators:** `data-pjx-loading="skeleton"` (or `"spinner"`) on any element inside a reactive root template flags it while an in-flight request dirties keys the region reacts to, until the swap lands. Scoping is by the enclosing `[data-pjx-id][data-pjx-reacts]` element, and the framework does **not** stamp `data-pjx-reacts` — render it on the reactive root yourself (`data-pjx-reacts="todos"`, space-joined keys) or nothing fires. A trigger may add `data-pjx-loading-extra="<css-selector>"` to also flag regions a bulk action will touch. Style via `--pjx-*` CSS vars (`--pjx-skeleton-color`, `--pjx-spinner-color`, …).
- Every `load()` is memoized in `LoadCache`, one entry per `(type, key)`. The cache is scoped to the enclosing `request_scope()` — each request gets a fresh store and it is discarded when the scope exits. There is no process-wide or cross-worker cache backend.

Full guide: [docs/reactivity.md](../reactivity.md).

## Builtins (`pyjinhx.builtins`)

`import pyjinhx.builtins` registers its optional components (`import pyjinhx.builtins as b; b.__all__` is the source of truth) — `PJXAccordion`, `PJXAlert`, `PJXButton`, `PJXCard`, `PJXDrawer`, `PJXDropdown`, `PJXLazyLoad`, `PJXModal`, `PJXPaginator`, `PJXPopover`, `PJXTable`, `PJXTabGroup`, and the rest. Same `BaseComponent` rules; each one's `.py`, `.pjx`, `.css` and `.js` share a snake_case stem under `pyjinhx/builtins/**/pjx_<component>/`, and the renderer falls back to on-disk templates if the app's Jinja loader can't see package templates. **Do not** register user subclasses with the same class name as a builtin — the global `Registry` is one class per name.

- **Host theme** (set on `:root` or a wrapper): builtin CSS reads shared tokens — define at least `--surface`, `--surface-alt`, `--text`, `--text-muted`, `--border`, `--brand`, `--brand-subtle`, `--brand-muted`, `--error`, `--success`, `--warning`, `--font-size-{xs,sm,md}`, `--radius-{sm,md,lg,full}`, `--shadow-md`, `--transition`, `--space-3`, `--space-4`. Optional `--error-bg` / `--error-border` for error surfaces (badge/alert fall back with `color-mix`).
- **Per-component tokens:** each stylesheet declares `--pjx-<widget>-*` properties on `:root` — override to tune one component without editing package files (e.g. `--pjx-modal-width`, `--pjx-dropdown-z`, `--pjx-drawer-width`).
- **Classes** are BEM: `pjx-<widget>`, `pjx-<widget>__element`, `pjx-<widget>--modifier`. Every builtin accepts `class_name` (appended on the root) and `extra_attrs` (validated dict rendered on the root).
- **PascalCase tag quirks:** `PJXBreadcrumb.items` accepts a JSON-string attribute in tag strings (the dict/list equivalent). JS components use `window.pjx.*` APIs (`pjx.modal.open/close`, `pjx.drawer.open/close`, `pjx.popover.open/close/toggle`, `pjx.notification.show/hide`, `pjx.loader.region.show/hide/reset/wrap`, `pjx.toast`, `pjx.pageLoader.*`); `PJXTabGroup`, `PJXTooltip` use delegated events with no exported API.

Full reference (props, classes, `--pjx-*` tokens, JS helpers per component): [Components](../components.md).

## Registry & configuration

Two registries, deliberately separate. Classes register once at definition/discovery time under their snake_case tag name — that is the one PascalCase tags resolve through. Instances register **after they render**, under the composite key `ClassName_id` (so different types can share an id), into a request-scoped store used only by reactivity; `PjxScopeMiddleware` subscribes `register_rendered_instance` for you under `setup(app)`. A miss there is routine, never "the region is gone". Outside a wired app, isolate per request yourself with `from pyjinhx.session import request_scope; with request_scope(): ...` — `pyjinhx.session` is an internal module, not public API, so prefer `setup(app)` wherever it works.

Set the components/template root via `setup(components_root="./components")` (or `PjxSettings(components_root=...)`); see [Configuration](../guide/configuration.md) for the full settings surface.

`request_scope()` takes `session=` and `load_context=` only — there is no `template_dir` argument, and `RenderSession()` takes none at all.

Keep each component's `.py`, template, and optional assets together under one snake_case stem, e.g. `components/ui/button/button.{py,pjx,js,css}`.

## Public API

```python
from pyjinhx import (
    BaseComponent,      # base class for all components
    Slot,               # field type for raw-HTML/icon/component values (opt out of escaping)
    Children,           # tag inner content field type
    component,          # classless-component decorator
    ReactiveComponent,  # react={...} + classmethod load(); routes return Cls.load(...)
    render,             # free-function render(component, session=None) -> str
    RenderSession,       # per-request render state
    setup,               # process config + optional framework middleware wiring
    PjxContext,          # read-only per-request context (session, dirtied keys, load context)
    mutates,             # decorator on store methods; state keys only
    dirty,               # mark MutationKey members dirty outside a @mutates call
    MutationKey,         # base class for declaring your own reactive keys
    reactive_key,        # helper for defining MutationKey members
    PjxKey,              # Annotated[..., PjxKey()] marker for keyed regions
    AppContext,          # app-level context container
    PjxSettings,         # process settings (components_root, static_root, ...)
    AssetMode,           # INLINE / LINK / NONE asset delivery modes
)
# Everything above is `pyjinhx.__all__` — the supported surface.
# Below: internal modules. NOT public API, no stability guarantee; reach for
# them only when the public surface has no equivalent.
from pyjinhx.assets import all_assets           # (css_paths, js_paths) for every registered class
from pyjinhx.session import request_scope       # per-request isolation context manager
from pyjinhx.responses import compose, PjxResponse, PASSTHROUGH  # handler return -> wire response
from pyjinhx.reactive.fanout import oob_swaps, walk_manifest     # manual OOB walk (tests/advanced)
from pyjinhx.client.inject import PJX_MOUNTED_HEADER, PJX_TRIGGER_HEADER
import pyjinhx.builtins                         # optional: registers all builtin classes
```
````

## Usage

After creating the file, use the `/pyjinhx` command in Claude Code before asking it to build components. Claude will then follow PyJinHx conventions automatically — correct file placement, naming, nesting patterns, and rendering approach.
