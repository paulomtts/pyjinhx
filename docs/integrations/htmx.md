# HTMX

PyJinHx components work seamlessly with [HTMX](https://htmx.org/) for building interactive web applications with minimal JavaScript.

## Setup

Install PyJinHx:

```bash
pip install pyjinhx
```

### HTMX delivery

HTMX is the transport for PyJinHx reactivity (the client runtime `pjx.js`
depends on it). You don't have to add it yourself: on a **reactive root render**
PyJinHx inlines a pinned, vendored copy of HTMX ahead of `pjx.js`, so reactivity
works out of the box.

If you prefer to manage HTMX yourself — to pin a version, add extensions, or
serve it from your own CDN — include it in your layout as usual:

```html
<script src="https://unpkg.com/htmx.org@2.0.3"></script>
```

Nothing else is needed to make the two copies coexist: the inlined one
self-guards with `if (!window.htmx)`, so it defers to whatever HTMX your page
already loaded and never double-loads.

There is no off-switch to reach for. `PjxSettings.inject_htmx` (settable as
`setup(app, inject_htmx=False)` or `PJX_INJECT_HTMX=false`) is **recorded on the
settings object and not read anywhere** — how it should map onto the session's
asset modes is still open design. Treat auto-injection as always on, and rely on
the self-guard.

If HTMX ends up missing at runtime, `pjx.js` logs a clear `console.error`
instead of failing silently.

## Project Structure

```
my_app/
└── components/
    ├── ui/
    │   ├── button.py
    │   ├── button.pjx
    │   ├── counter.py
    │   ├── counter.pjx
    │   └── counter.js
    ├── page.py
    └── page.pjx
```

Templates are `<snake_case>.pjx` files sitting next to the module that defines
the component — never `.html` or `.jinja`, never kebab-case. Co-located assets
share the same stem (`counter.pjx` → `counter.js`).

## Basic Example

### Component Class

```python
# components/ui/button.py
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    endpoint: str = "/clicked"
```

### Component Template with HTMX

```html
<!-- components/ui/button.pjx -->
<button
    id="{{ id }}"
    hx-post="{{ endpoint }}"
    hx-vals='{"button_id": "{{ id }}"}'
    hx-target="#result"
    hx-swap="innerHTML"
>
    {{ text }}
</button>
```

### Page

The PascalCase `<Button>` tag is resolved by the PyJinHx renderer, so the page
that uses it is itself a component template — a `.pjx` file, not a hand-written
`index.html`:

```python
# page.py
from pyjinhx import BaseComponent


class Page(BaseComponent):
    pass
```

```html
<!-- page.pjx -->
<html>
<body>
    <Button id="click-me" text="Click Me" endpoint="/clicked"></Button>
    <div id="result"></div>
</body>
</html>
```

There's no separate "process this HTML string" step — a route builds the
component and returns it:

```python
from pyjinhx import setup

setup(app, components_root="./components")


@app.get("/")
def index():
    return Page(id="page")
```

You never have to add the `<script>` tag for HTMX yourself; PyJinHx inlines its
vendored copy on a reactive root render (see [HTMX delivery](#htmx-delivery)).

## Counter Example

A complete example showing state management with HTMX.

### Counter Component

```python
# components/ui/counter.py
from pyjinhx import BaseComponent


class Counter(BaseComponent):
    id: str
    value: int = 0
```

```html
<!-- components/ui/counter.pjx -->
<div id="{{ id }}" class="counter">
    <button
        hx-post="/counter/decrement"
        hx-vals='{"counter_id": "{{ id }}", "value": "{{ value }}"}'
        hx-target="#{{ id }}"
        hx-swap="outerHTML"
    >
        -
    </button>

    <span class="value">{{ value }}</span>

    <button
        hx-post="/counter/increment"
        hx-vals='{"counter_id": "{{ id }}", "value": "{{ value }}"}'
        hx-target="#{{ id }}"
        hx-swap="outerHTML"
    >
        +
    </button>
</div>
```

### Component JavaScript

```javascript
// components/ui/counter.js
document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.classList.contains('counter')) {
        console.log('Counter was updated!');
        // Add any additional client-side logic here
    }
});
```

## HTMX Patterns with PyJinHx

### Target a component by id and swap `outerHTML`

When a route returns a full component, pass its `id` in the request (so the
server can target the right element) and use `hx-swap="outerHTML"` to replace
the whole element with the response:

```html
<!-- components/ui/item.pjx -->
<div id="{{ id }}" class="item">
    <h3>{{ title }}</h3>
    <button
        hx-post="/items/{{ id }}/update"
        hx-vals='{"item_id": "{{ id }}"}'
        hx-target="#{{ id }}"
        hx-swap="outerHTML"
    >
        Update
    </button>
</div>
```

### Conditional HTMX Attributes

Use Jinja conditionals to control HTMX behavior:

```html
<!-- components/ui/button.pjx -->
<button
    id="{{ id }}"
    {% if endpoint %}
    hx-post="{{ endpoint }}"
    hx-target="#result"
    hx-swap="innerHTML"
    {% endif %}
>
    {{ text }}
</button>
```

### `PJXTabGroup` outside the swap target

A [`PJXTabGroup`](../components.md#pjxtabgroup) holds multiple panels (e.g. chat vs. other tools) while standalone [`PJXTab`](../components.md#pjxtab) triggers can live in a navbar or sidebar. To **keep in-DOM state** (messages, inputs) when other UI updates, mount the **`PJXTabGroup` root outside** the element you pass to `hx-target` for those swaps. Only swap inner fragments that should reload; avoid replacing the entire `PJXTabGroup` wrapper unless you intend to reset that state.

### Wiring builtins (pure passthrough)

Builtins never require htmx and degrade to plain HTML on their own. To add htmx
behaviour, attach `hx-*` attributes directly to the element you author in your
template. For a builtin's root element the framework's attribute passthrough
carries them onto the rendered HTML element — no wrapper `<div>` needed.

**Worked example — server-driven sortable table header**

A `PJXTableHeaderCell` already renders a `<th>` with an inner `<button>` for
keyboard operability. Add `hx-*` attributes and the builtin becomes a live sort
control with no custom JS:

```html
<PJXTableHeaderCell sortable="true" sort="asc"
    hx-get="/users?sort=name&dir=desc" hx-target="#users-table" hx-swap="outerHTML">
  Name
</PJXTableHeaderCell>
```

How it works:

- The `hx-*` attributes land on the rendered `<th>`.
- The inner `<button>` makes the cell keyboard-operable; a click bubbles up to
  the `<th>`, where htmx intercepts and fires the request.
- The server responds with a re-sorted table fragment carrying updated `sort` /
  `aria-sort` values — no JS ships with the component.

The same passthrough applies to any builtin: for example, add `hx-post="/action"`
to a `PJXButton` and htmx picks it up on the rendered `<button>` element.

### Loading states

For ad-hoc cases you can use htmx's own [`hx-indicator`](https://htmx.org/attributes/hx-indicator/)
with a `.htmx-indicator` element. For reactive components, PyJinHx ships built-in
indicators instead: add `data-pjx-loading="skeleton"` or `data-pjx-loading="spinner"`
to the element(s) that should show an in-flight effect — no extra markup or CSS
needed. A trigger can also name extra regions to light with
`data-pjx-loading-extra="<css-selector>"`, and every effect is themable through
`--pjx-*` CSS custom properties. See [Loading indicators](../reactivity.md#loading-indicators-in-flight).

## How PyJinHx talks to htmx

`pjx.js` (auto-included with reactive components) hooks a few htmx events. You
don't call these yourself, but it helps to know what's on the wire:

- On **`htmx:configRequest`** it stamps three request headers the server reads to
  decide what to re-render: `X-PJX-Mounted` (the manifest of mounted components),
  `X-PJX-Assets` (already-loaded script/stylesheet URLs, so they aren't re-sent),
  and `X-PJX-Trigger` (the component that triggered the request).
- The loading-indicator lifecycle is driven from htmx events: it lights indicators
  on **`htmx:beforeRequest`**, re-applies them across swaps on **`htmx:afterSettle`**,
  and clears them on **`htmx:afterOnLoad`** (plus the error/abort events
  `htmx:responseError`, `htmx:timeout`, `htmx:sendError`, and `htmx:abort`).

## Tips

### Component JavaScript with HTMX Events

If your component has JavaScript that needs to run after HTMX swaps, use HTMX events:

```javascript
// components/ui/widget.js
document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.classList.contains('widget')) {
        // Initialize widget after swap
        initializeWidget(event.detail.target);
    }
});
```

### Server-Sent Events and WebSockets

These aren't PyJinHx-specific. In htmx 2 the old `hx-sse` / `hx-ws` core
attributes are gone — SSE and WebSockets are now opt-in extensions
(`hx-ext="sse"` with `sse-connect`, `hx-ext="ws"` with `ws-connect`). See htmx's
[SSE](https://htmx.org/extensions/sse/) and [WebSocket](https://htmx.org/extensions/ws/)
extension docs, and render the streamed fragments with PyJinHx components as usual.

## Dependency-aware updates (reactive OOB)

The patterns above use manual `hx-target` / `hx-swap` for each interaction. With
PyJinHx reactivity, a mutation route simply returns `Cls(...)` and every
dependent region rides along as an `hx-swap-oob` fragment — no per-swap wiring.
This is the path to reach for when **one mutation updates multiple regions**
(counter, list, totals):

- Declare `react={...}` + a `@classmethod load(cls, <PjxKey fields>)` factory on `ReactiveComponent` subclasses
- Construct the primary and `return <instance>` from mutation routes — dependent regions ride along as `hx-swap-oob` fragments
- Wire the app with `setup(app)` so the request scope, the header parsing and the response adapter are in place

The OOB legs are attached by the response composer as it turns your return value
into a response — not by `render()`, which only ever gives you one component's
markup and never appended anything else. What earns the fan-out is *returning*
from the handler, so returning `Cls(...)` and returning a string both get it;
returning the component is simply the shorter spelling.

See [Response composition](../api/responses.md), [Reactivity](../reactivity.md)
and [Usage tiers](../guide/usage-tiers.md).

## Response edges pyjinhx smooths

### Reactive triggers don't need `hx-swap="none"`

A response with no primary HTML is OOB-only: htmx applies the out-of-band swaps,
then swaps the empty leftover into the trigger's target — clearing it. pyjinhx
removes this footgun automatically: when a handler returns `None` (or an empty
primary), the composer emits `HX-Reswap: none`, so the trigger keeps its content
with no extra attribute:

```html
<!-- no hx-swap="none" needed -->
<button hx-get="/nav?route=chat">Chat</button>
```

This is always on and requires the pyjinhx middleware (installed by
`setup(app)`).

### Making redirects navigate under htmx

htmx AJAX-follows a `3xx` and swaps the destination page into a fragment instead
of navigating. You do not need a pyjinhx-specific response for this: return your
framework's own redirect and pyjinhx translates it.

```python
from fastapi.responses import RedirectResponse


@app.post("/logout")
def logout():
    return RedirectResponse("/login", status_code=303)
```

For an **htmx** request, any handler return whose `status_code` falls in 300–399 and
that carries a `Location` header becomes `204 No Content` with `HX-Redirect: /login`,
which htmx turns into a real browser navigation. The check is duck-typed on that shape,
so hand-built and third-party redirect responses translate too. A **plain** (non-htmx)
navigation gets the real `3xx` back, untouched — the same route serves both.

`HX-Location` — htmx's client-side ajax navigation — has no status-code spelling, so
there is nothing for pyjinhx to translate from. Ask for it directly:

```python
from starlette.responses import Response


@app.post("/logout")
def logout():
    return Response(status_code=204, headers={"HX-Location": "/login"})
```

A framework `Response` is not a shape `compose()` adapts, so it takes the `PASSTHROUGH`
path and reaches the client exactly as written.

There is no pyjinhx `redirect()` helper and no setting for any of this — the
translation is always on. See [Response composition](../api/responses.md).

### The `HX-Reswap: none` mechanism

The automatic `HX-Reswap: none` behavior described above is implemented in
`pyjinhx/responses.py`: `compose()` emits it whenever the composed body has no
primary markup. There's no pluggable backend hook for this — it's a fixed
property of composition, so every backend agrees about it. Framework glue
(mounting static files, request scoping, adapting a pjx return into a native
response) is the seam that *is* pluggable, via the
[`IntegrationBackend`](../api/client-backend.md) protocol that `setup()` wires
up per framework. The full set of shapes `compose()` accepts is documented in
[Response composition](../api/responses.md).
