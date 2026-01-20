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

## FastAPI + HTMX + WebAwesome

This example shows how to integrate PyJinHx with [WebAwesome](https://webawesome.com/) - a comprehensive web components library that provides 50+ customizable UI components built on web standards.

### Setup

```bash
pip install fastapi uvicorn pyjinhx
```

You'll also need a WebAwesome project. Sign up at [webawesome.com](https://webawesome.com/) to get your project code, or use the NPM package.

### Project Structure

```
my_app/
├── components/
│   └── ui/
│       ├── task_card.py
│       ├── task_card.html
│       ├── add_task_form.py
│       └── add_task_form.html
├── main.py
└── pyproject.toml
```

### Task Card Component

Wraps a WebAwesome card with task content:

```python
# components/ui/task_card.py
from pyjinhx import BaseComponent


class TaskCard(BaseComponent):
    id: str
    title: str
    description: str
    completed: bool = False
```

```html
<!-- components/ui/task_card.html -->
<wa-card id="task-{{ id }}" appearance="outlined" style="margin-bottom: 1rem;">
    <div slot="header">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <wa-checkbox
                {% if completed %}checked{% endif %}
                hx-post="/tasks/{{ id }}/toggle"
                hx-target="#task-{{ id }}"
                hx-swap="outerHTML"
            ></wa-checkbox>
            <span style="{% if completed %}text-decoration: line-through; opacity: 0.6;{% endif %}">
                {{ title }}
            </span>
        </div>
    </div>

    <p style="{% if completed %}opacity: 0.6;{% endif %}">{{ description }}</p>

    <div slot="footer" style="display: flex; gap: 0.5rem;">
        <wa-button
            variant="{% if completed %}neutral{% else %}success{% endif %}"
            size="small"
            hx-post="/tasks/{{ id }}/toggle"
            hx-target="#task-{{ id }}"
            hx-swap="outerHTML"
        >
            <wa-icon slot="start" name="{% if completed %}rotate-left{% else %}check{% endif %}"></wa-icon>
            {% if completed %}Mark Incomplete{% else %}Complete{% endif %}
        </wa-button>

        <wa-button
            variant="danger"
            size="small"
            hx-delete="/tasks/{{ id }}"
            hx-target="#task-{{ id }}"
            hx-swap="outerHTML"
            hx-confirm="Are you sure you want to delete this task?"
        >
            <wa-icon slot="start" name="trash"></wa-icon>
            Delete
        </wa-button>
    </div>
</wa-card>
```

### Add Task Form Component

```python
# components/ui/add_task_form.py
from pyjinhx import BaseComponent


class AddTaskForm(BaseComponent):
    pass
```

```html
<!-- components/ui/add_task_form.html -->
<wa-card appearance="filled">
    <div slot="header">Add New Task</div>

    <form
        hx-post="/tasks/add"
        hx-target="#task-list"
        hx-swap="afterbegin"
        hx-on::after-request="this.reset()"
    >
        <div style="display: flex; flex-direction: column; gap: 1rem;">
            <wa-input
                name="title"
                label="Task Title"
                required
                placeholder="Enter task title"
            ></wa-input>

            <wa-input
                name="description"
                label="Description"
                placeholder="Enter task description"
            ></wa-input>

            <wa-button type="submit" variant="brand">
                <wa-icon slot="start" name="plus"></wa-icon>
                Add Task
            </wa-button>
        </div>
    </form>
</wa-card>
```

### FastAPI Application

```python
# main.py
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from pyjinhx import Renderer
from components.ui.task_card import TaskCard
from components.ui.add_task_form import AddTaskForm

Renderer.set_default_environment("./components")

app = FastAPI()

# In-memory task storage (use a database in production)
tasks = {
    "1": {
        "title": "Learn PyJinHx",
        "description": "Understand how to build reusable components",
        "completed": True
    },
    "2": {
        "title": "Integrate WebAwesome",
        "description": "Use WebAwesome components in your app",
        "completed": False
    },
    "3": {
        "title": "Add HTMX interactions",
        "description": "Make the UI dynamic without JavaScript",
        "completed": False
    },
}
next_id = 4


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    task_list = "\n".join([
        TaskCard(
            id=task_id,
            title=task["title"],
            description=task["description"],
            completed=task["completed"]
        ).render()
        for task_id, task in tasks.items()
    ])

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Task Manager - PyJinHx + WebAwesome</title>

        <!-- WebAwesome - Replace with your project code from webawesome.com -->
        <script type="module" src="https://cdn.jsdelivr.net/npm/@awesome.me/webawesome@latest/dist/webawesome.js"></script>

        <!-- HTMX -->
        <script src="https://unpkg.com/htmx.org@1.9.10"></script>

        <style>
            body {{
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 800px;
                margin: 2rem auto;
                padding: 0 1rem;
                background: #f5f5f5;
            }}
            h1 {{
                margin-bottom: 2rem;
            }}
            #task-list {{
                margin-top: 2rem;
            }}
        </style>
    </head>
    <body>
        <h1>Task Manager</h1>

        {AddTaskForm().render()}

        <div id="task-list">
            {task_list}
        </div>
    </body>
    </html>
    """


@app.post("/tasks/add", response_class=HTMLResponse)
def add_task(title: str = Form(...), description: str = Form("")) -> str:
    global next_id
    task_id = str(next_id)
    next_id += 1

    tasks[task_id] = {{
        "title": title,
        "description": description,
        "completed": False
    }}

    return TaskCard(
        id=task_id,
        title=title,
        description=description,
        completed=False
    ).render()


@app.post("/tasks/{{task_id}}/toggle", response_class=HTMLResponse)
def toggle_task(task_id: str) -> str:
    if task_id in tasks:
        tasks[task_id]["completed"] = not tasks[task_id]["completed"]
        return TaskCard(
            id=task_id,
            title=tasks[task_id]["title"],
            description=tasks[task_id]["description"],
            completed=tasks[task_id]["completed"]
        ).render()
    return ""


@app.delete("/tasks/{{task_id}}", response_class=HTMLResponse)
def delete_task(task_id: str) -> str:
    if task_id in tasks:
        del tasks[task_id]
    return ""  # Return empty to remove the element
```

### Run the Application

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000` to see the task manager in action with WebAwesome components integrated seamlessly with PyJinHx and HTMX.

### Key Features

- **WebAwesome Components**: Uses native web components (`<wa-card>`, `<wa-button>`, `<wa-input>`, `<wa-checkbox>`, `<wa-icon>`)
- **PyJinHx Wrapping**: Each WebAwesome component is wrapped in a PyJinHx component for reusability
- **HTMX Interactivity**: Add, toggle, and delete tasks without writing JavaScript
- **Form Handling**: WebAwesome inputs with FastAPI form processing
- **Component Slots**: Leverages WebAwesome's slot system for flexible layouts
- **Type Safety**: Pydantic-based component props ensure type safety
- **No Build Step**: WebAwesome loads via CDN, no bundler required

### How It Works Together

1. **PyJinHx Components** wrap WebAwesome web components, providing:
   - Type-safe props via Pydantic
   - Template rendering via Jinja2
   - Reusable component structure

2. **WebAwesome** provides the UI layer:
   - Professional, accessible components
   - Built-in styling and themes
   - Native web component features (slots, events)

3. **HTMX** handles interactivity:
   - Partial page updates
   - Form submissions
   - Delete confirmations
   - No JavaScript framework needed

4. **FastAPI** serves the components:
   - Type-safe endpoints
   - Form handling
   - Component rendering on the server

This stack gives you the benefits of modern web components, server-side rendering, and progressive enhancement without complex JavaScript frameworks.

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
