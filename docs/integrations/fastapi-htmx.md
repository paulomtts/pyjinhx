# FastAPI + HTMX

PyJinHx works great with FastAPI and HTMX for building interactive web applications with minimal JavaScript.

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
│       ├── counter.py
│       └── counter.html
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
    endpoint: str = "/clicked"
```

### Component Template (with HTMX)

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
        <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    </head>
    <body>
        {Button(id="click-me", text="Click Me").render()}
        <div id="result"></div>
    </body>
    </html>
    """


@app.post("/clicked", response_class=HTMLResponse)
def clicked(button_id: str = "unknown") -> str:
    return f"<p>Button '{button_id}' was clicked!</p>"
```

Run with:

```bash
uvicorn main:app --reload
```

## Counter Example

A more complete example showing state management.

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

### FastAPI Routes

```python
from components.ui.counter import Counter


@app.get("/counter", response_class=HTMLResponse)
def counter_page() -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://unpkg.com/htmx.org@1.9.10"></script>
        <style>
            .counter {{ display: flex; gap: 1rem; align-items: center; }}
            .counter button {{ padding: 0.5rem 1rem; }}
            .value {{ font-size: 2rem; min-width: 3rem; text-align: center; }}
        </style>
    </head>
    <body>
        <h1>Counter Demo</h1>
        {Counter(id="my-counter", value=0).render()}
    </body>
    </html>
    """


@app.post("/counter/increment", response_class=HTMLResponse)
def increment(counter_id: str, value: int) -> str:
    return Counter(id=counter_id, value=value + 1).render()


@app.post("/counter/decrement", response_class=HTMLResponse)
def decrement(counter_id: str, value: int) -> str:
    return Counter(id=counter_id, value=value - 1).render()
```

## Tips

### Use `hx-swap="outerHTML"` for Component Updates

When returning a full component, use `outerHTML` to replace the entire element:

```html
hx-target="#{{ id }}"
hx-swap="outerHTML"
```

### Pass Component ID in Requests

Include the component ID so you can target the right element:

```html
hx-vals='{"component_id": "{{ id }}"}'
```

### Combine with Jinja Base Templates

For larger apps, use Jinja extends/includes:

```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("./templates"))
Renderer.set_default_environment(env)

@app.get("/", response_class=HTMLResponse)
def index():
    template = env.get_template("index.html")
    return template.render(
        counter=Counter(id="main-counter", value=0)
    )
```

```html
<!-- templates/index.html -->
{% extends "base.html" %}

{% block content %}
    <h1>My App</h1>
    {{ counter }}
{% endblock %}
```

### Component JavaScript with HTMX

If your component has JavaScript that needs to run after HTMX swaps, use HTMX events:

```javascript
// counter.js
document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.classList.contains('counter')) {
        console.log('Counter was updated!');
    }
});
```
