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
│       ├── button.html
│       ├── card.py
│       └── card.html
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
<!-- components/ui/button.html -->
<button id="{{ id }}" class="btn btn-{{ variant }}">
    {{ text }}
</button>
```

### App

```python
# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from pyjinhx import Renderer
from components.ui.button import Button

Renderer.set_default_environment("./components")

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

For larger applications, combine PyJinHx components with Jinja2 page templates:

```python
from jinja2 import Environment, FileSystemLoader
from pyjinhx import Renderer

env = Environment(loader=FileSystemLoader("./templates"))
Renderer.set_default_environment(env)

@app.get("/", response_class=HTMLResponse)
def index():
    template = env.get_template("index.html")
    return template.render(
        button=Button(id="main-btn", text="Click Me"),
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

## Request-Scoped Registry

In web apps, component instances from one request can leak into the next. Use `Registry.request_scope()` to isolate per request. See the [Registry guide](../guide/registry.md) for details.

### Per-Route

```python
from pyjinhx import Registry

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    with Registry.request_scope():
        return f"""
        <!DOCTYPE html>
        <html>
        <body>
            {Button(id="submit-btn", text="Submit").render()}
        </body>
        </html>
        """
```

### Middleware (recommended)

```python
from starlette.middleware.base import BaseHTTPMiddleware


class RegistryScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        with Registry.request_scope():
            return await call_next(request)


app.add_middleware(RegistryScopeMiddleware)
```

## Tips

- **Component assets**: Components with adjacent `.js` and `.css` files have their assets auto-injected. See [Asset Collection](../guide/assets.md).
- **Response types**: FastAPI's `HTMLResponse` works directly with `render()`, which returns `Markup` objects that convert to strings automatically.
