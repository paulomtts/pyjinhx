# FastAPI

PyJinHx integrates seamlessly with [FastAPI](https://fastapi.tiangolo.com/) for server-side rendered components.

## Setup

```bash
pip install fastapi uvicorn pyjinhx
```

## Project Structure

```
my_app/
├── components/
│   └── ui/
│       ├── button.py
│       ├── button.pjx
│       ├── card.py
│       └── card.pjx
├── main.py
└── pyproject.toml
```

## Basic Example

### Component

```python
# components/ui/button.py
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    variant: str = "primary"
```

```html
<!-- components/ui/button.pjx -->
<button id="{{ id }}" class="btn btn-{{ variant }}">
    {{ text }}
</button>
```

### App

```python
# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from components.ui.button import Button

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Welcome</h1>
        {Button(id="submit-btn", text="Submit", variant="primary").render()}
        {Button(id="cancel-btn", text="Cancel", variant="secondary").render()}
    </body>
    </html>
    """
```

```bash
uvicorn main:app --reload
```

## Using Jinja Base Templates

For larger applications, combine PyJinHx components with Jinja2 page templates.
A plain Jinja environment knows nothing about PyJinHx tags, so pass **rendered
markup**, not the component instance — render it and wrap it in `Markup` so
autoescaping leaves it alone:

```python
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

env = Environment(loader=FileSystemLoader("./templates"), autoescape=True)


@app.get("/", response_class=HTMLResponse)
def index():
    template = env.get_template("index.html")
    return template.render(
        button=Markup(Button(id="main-btn", text="Click Me").render()),
    )
```

```html
<!-- templates/index.html -->
{% extends "base.html" %}

{% block content %}
    <h1>My App</h1>
    {{ button }}
{% endblock %}
```

Passing the instance itself prints its pydantic repr (escaped, if the
environment autoescapes) — a `BaseComponent` has no `__str__` or `__html__`
that renders it. The PascalCase `<Button ...>` tag form only works inside a
PyJinHx `.pjx` template, where the renderer resolves tags; if you want to write
tags for your page shell, make the page a component with its own `.pjx`
template instead of an external Jinja one.

## Request-Scoped Registry { #middleware-recommended }

In web apps, component instances from one request can leak into the next. The recommended setup is a single call:

```python
from fastapi import FastAPI
from pyjinhx import setup

app = FastAPI(lifespan=my_existing_lifespan)  # optional — chained, not replaced
setup(app, context_factory=lambda req: AppLoadContext(db=get_db(req)))
```

`setup(app, ...)` chains your lifespan (if any) and registers registry middleware with the `FastAPIBackend` (an `IntegrationBackend`) for header auto-resolution. See [Configuration](../api/config.md) and [Reactivity → load() results are cached](../reactivity.md#load-results-are-cached).

### Per-Route (manual)

```python
from pyjinhx.session import request_scope


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    with request_scope():
        return f"""
        <!DOCTYPE html>
        <html>
        <body>
            {Button(id="submit-btn", text="Submit").render()}
        </body>
        </html>
        """
```

!!! warning "A bare `request_scope()` is not a substitute for `setup(app)`"
    `request_scope()` only isolates the per-request state (session, instance
    registry, dirtied keys, load cache). It builds a plain `RenderSession` with
    **no render hooks attached**, so inside it you get:

    - no asset accumulation — components' `.js`/`.css` are never collected,
    - no reactive root stamping — no `data-pjx-id` / `-type` / `-hash` / `-load`,
      so nothing on the page is addressable by the client runtime,
    - no instance registration — the request-scoped instance registry stays empty.

    Reactivity needs all three. Use it only for non-reactive rendering in an app
    you cannot wire with `setup(app)`.

    Do **not** nest it inside an app that `setup(app)` already wired: the
    middleware's hooked session is the current one for the request, and opening
    a fresh scope inside a handler shadows it with an unhooked session for the
    duration of the block. If you need your own session there, build it, attach
    the hooks yourself, and pass it as `request_scope(session=my_session)`.
    `request_scope()` takes `session=` and `load_context=` only; the components
    root is a process-level setting (`setup(components_root=...)`).

### Advanced: manual middleware

If you cannot use `setup(app)`, define middleware yourself — see [Client Backend](../api/client-backend.md) and [Registry guide](../guide/registry.md).

Pair with `@mutates` on store methods so mutation routes never have to name the
dirtied keys themselves — see [Reactivity](../reactivity.md#mutation-tracking-mutates)
and [Client Backend](../api/client-backend.md).

Reactive mutation routes **return the component**; they do not render it:

```python
@app.post("/rows/{todo_id}/toggle")
def toggle_row(todo_id: int):
    store.toggle(todo_id)
    return TodoItemRow(todo_id=todo_id, id=f"row-{todo_id}")
```

The returned component becomes the primary fragment, and every mounted region
whose `react` keys `store.toggle`'s `@mutates` dirtied is appended as an
`hx-swap-oob` fragment. That fan-out is attached by the response composer as it
turns the handler's return value into a response — never by `render()`, which
hands back one component's markup and nothing else. See
[Response composition](../api/responses.md).

## Tips

- **Component assets**: Components with adjacent `.js` and `.css` files — same snake_case stem as the `.pjx`, e.g. `todo_counter.py` / `todo_counter.pjx` / `todo_counter.js` — have their assets auto-injected. See [Asset Collection](../guide/assets.md).
- **Response types**: FastAPI's `HTMLResponse` works directly with `render()`, which returns a plain `str`. Under `setup(app)` you can also just return the component (or a plain string) and let the composer build the response — see [Response composition](../api/responses.md).
