# FastAPI

PyJinHx integrates seamlessly with [FastAPI](https://fastapi.tiangolo.com/) for building web applications with server-side rendered components.

## Setup

Install the required packages:

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

### Component Class

```python
# components/ui/button.py
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    variant: str = "primary"
```

### Component Template

```html
<!-- components/ui/button.html -->
<button
    id="{{ id }}"
    class="btn btn-{{ variant }}"
>
    {{ text }}
</button>
```

### FastAPI App

```python
# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from pyjinhx import Renderer
from components.ui.button import Button

# Configure template path
Renderer.set_default_environment("./components")

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>My App</title>
        <style>
            .btn {{
                padding: 0.5rem 1rem;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }}
            .btn-primary {{
                background: #007bff;
                color: white;
            }}
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
        </style>
    </head>
    <body>
        <h1>Welcome</h1>
        {Button(id="submit-btn", text="Submit", variant="primary").render()}
        {Button(id="cancel-btn", text="Cancel", variant="secondary").render()}
    </body>
    </html>
    """
```

Run with:

```bash
uvicorn main:app --reload
```

## Card Component Example

A more complete example with nested components.

### Card Component

```python
# components/ui/card.py
from pyjinhx import BaseComponent


class Card(BaseComponent):
    id: str
    title: str
    content: str
```

```html
<!-- components/ui/card.html -->
<div id="{{ id }}" class="card">
    <div class="card-header">
        <h3>{{ title }}</h3>
    </div>
    <div class="card-body">
        <p>{{ content }}</p>
    </div>
</div>
```

### FastAPI Routes

```python
from components.ui.card import Card


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    cards = [
        Card(
            id="card-1",
            title="Users",
            content="Total users: 1,234"
        ),
        Card(
            id="card-2",
            title="Revenue",
            content="Total revenue: $45,678"
        ),
        Card(
            id="card-3",
            title="Orders",
            content="Total orders: 567"
        ),
    ]
    
    cards_html = "\n".join([card.render() for card in cards])
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
        <style>
            .card {{
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 1rem;
                margin: 1rem 0;
            }}
            .card-header h3 {{
                margin: 0 0 0.5rem 0;
            }}
        </style>
    </head>
    <body>
        <h1>Dashboard</h1>
        {cards_html}
    </body>
    </html>
    """
```

## Using Jinja Templates

For larger applications, combine PyJinHx components with Jinja2 base templates:

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
        card=Card(id="main-card", title="Welcome", content="Hello, World!")
    )
```

```html
<!-- templates/index.html -->
{% extends "base.html" %}

{% block content %}
    <h1>My App</h1>
    {{ card }}
    {{ button }}
{% endblock %}
```

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My App{% endblock %}</title>
    {% block head %}{% endblock %}
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
```

## Request-Scoped Registry

When handling multiple requests, component instances registered in one request can persist and cause "Overwriting..." warnings on subsequent requests that use the same component IDs. The `Registry.request_scope()` context manager solves this by providing isolated registries per request.

### Basic Usage

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from pyjinhx import Registry, Renderer
from components.ui.button import Button

Renderer.set_default_environment("./components")

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    with Registry.request_scope():
        # Components registered here are isolated to this request
        return f"""
        <!DOCTYPE html>
        <html>
        <body>
            {Button(id="submit-btn", text="Submit").render()}
        </body>
        </html>
        """
```

### Using Middleware

For application-wide coverage, use middleware to wrap all requests:

```python
from starlette.middleware.base import BaseHTTPMiddleware


class RegistryScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        with Registry.request_scope():
            return await call_next(request)


app.add_middleware(RegistryScopeMiddleware)


# Now all routes automatically have isolated registries
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body>
        {Button(id="submit-btn", text="Submit").render()}
    </body>
    </html>
    """
```

### How It Works

- On entering the context, a fresh empty registry is created
- Components instantiated inside the scope are registered in this isolated registry
- On exiting the context (even if an exception occurs), the previous registry state is restored
- Nested scopes are supported—each creates its own isolated registry

## Tips

### Component JavaScript

Components can include JavaScript files that are automatically collected:

```python
# components/ui/modal.py
class Modal(BaseComponent):
    id: str
    title: str
    content: str
    js: list[str] = ["components/ui/modal.js"]
```

The JavaScript file will be automatically injected when the component is rendered.

### Form Handling

Use FastAPI's form handling with PyJinHx components:

```python
from fastapi import Form

@app.post("/submit", response_class=HTMLResponse)
def submit_form(
    name: str = Form(...),
    email: str = Form(...)
) -> str:
    # Process form data
    return f"""
    <div class="success">
        <p>Thank you, {name}!</p>
        <p>We'll contact you at {email}.</p>
    </div>
    """
```

### Response Types

FastAPI's `HTMLResponse` works seamlessly with PyJinHx's `render()` method, which returns `Markup` objects that are automatically converted to strings.
