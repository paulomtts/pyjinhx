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

The inlined copy self-guards (`if (!window.htmx)`), so it never double-loads
when your page already provides HTMX. To turn auto-injection off entirely:

```python
setup(app, inject_htmx=False)   # or env: PJX_INJECT_HTMX=false
```

If HTMX ends up missing at runtime, `pjx.js` logs a clear `console.error`
instead of failing silently.

## Project Structure

```
my_app/
├── components/
│   └── ui/
│       ├── button.py
│       ├── button.html
│       ├── counter.py
│       ├── counter.html
│       └── counter.js
└── index.html
```

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
<!-- components/ui/button.html -->
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

### HTML Page

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/htmx.org@2.0.3"></script>
</head>
<body>
    <Button id="click-me" text="Click Me" endpoint="/clicked"></Button>
    <div id="result"></div>
</body>
</html>
```

Use PyJinHx's `Renderer` to process the HTML:

```python
from pyjinhx import Renderer

Renderer.set_default_environment("./components")

with open("index.html", "r") as f:
    source = f.read()

html = Renderer.get_default_renderer().render(source)
```

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
<!-- components/ui/counter.html -->
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
<!-- components/ui/item.html -->
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
<!-- components/ui/button.html -->
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
PyJinHx reactivity, a mutation route simply returns `Cls.render()` and every
dependent region rides along as an `hx-swap-oob` fragment — no per-swap wiring.
This is the path to reach for when **one mutation updates multiple regions**
(counter, list, totals):

- Declare `react={...}` + `load()` on `ReactiveComponent` subclasses
- Return `Cls.render()` from mutation routes — dependent regions ride along as `hx-swap-oob` fragments
- Wire [ClientBackend](../api/client-backend.md) via `setup()` so routes call `Cls.render()` with no framework kwargs

See [Reactivity](../reactivity.md), [Usage tiers](../guide/usage-tiers.md), and the [reactive todo example](https://github.com/paulomtts/pyjinhx/tree/master/examples/reactive_todo).

## Response edges pyjinhx smooths

### Reactive triggers don't need `hx-swap="none"`

A `ReactiveResponse` with no primary HTML is OOB-only: htmx applies the
out-of-band swaps, then swaps the empty leftover into the trigger's target —
clearing it. pyjinhx removes this footgun automatically: when a request produces
an OOB-only `ReactiveResponse`, the middleware emits `HX-Reswap: none`, so the
trigger keeps its content with no extra attribute:

```html
<!-- no hx-swap="none" needed -->
<button hx-get="/nav?route=chat">Chat</button>
```

This is always on and requires the pyjinhx middleware (installed by
`setup(app)`).

### Opt-in: make redirects navigate (`htmx_redirects=True`)

htmx AJAX-follows a `3xx` and swaps the destination page into a fragment instead
of navigating. Enable `setup(app, htmx_redirects=True)` and pyjinhx rewrites
`3xx → 204 + HX-Redirect` for htmx requests, so handlers stay transport-agnostic:

```python
setup(app, htmx_redirects=True)

@app.post("/logout")
def logout():
    return RedirectResponse("/login", status_code=303)  # browser navigates under htmx
```

`Set-Cookie` and other headers are preserved; `304 Not Modified` is left alone.
Defaults off so it never surprises apps that want htmx's swap behavior. You can
also set it via the `PJX_HTMX_REDIRECTS` environment variable.

### Custom client backends

Both behaviors are emitted via `ClientBackend.apply_response_directives(response)`.
The default applies the implied `HX-*` headers to any response with a mutable
`.headers` mapping, so a custom backend inherits the reactive `HX-Reswap`
behavior for free; override it only if your framework's response differs.
