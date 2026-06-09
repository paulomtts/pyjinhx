# WebAwesome

[WebAwesome](https://webawesome.com/) is a web-components library (50+ custom elements
built on web standards). It pairs well with PyJinHx, but there is no special integration:
**WebAwesome tags are just markup PyJinHx renders.** PyJinHx has no awareness of WebAwesome
— no asset auto-collection (the WA CDN/bundle `<script>` is the page author's
responsibility), and no reactive coupling. Loading the WA runtime, theming, and upgrading
the custom elements all happen client-side, exactly as in any HTML page.

!!! warning "Custom-element boolean/enum attributes need a Jinja guard"
    Custom elements treat an attribute as "on" by its **presence**, so `open="False"` or
    `open=""` still opens a dialog. Render boolean attrs with
    `{% if flag %}attr{% endif %}` (emit the attribute only when true), not
    `attr="{{ flag }}"`. The same applies to enum attrs you might leave blank.

## Setup

Install PyJinHx:

```bash
pip install pyjinhx
```

Include WebAwesome in your HTML. You can either:

1. Use the CDN (for development):
```html
<script type="module" src="https://cdn.jsdelivr.net/npm/@awesome.me/webawesome@latest/dist/webawesome.js"></script>
```

2. Use your project code from [webawesome.com](https://webawesome.com/) (recommended for production):
```html
<script type="module" src="https://cdn.webawesome.com/YOUR_PROJECT_CODE/webawesome.js"></script>
```

## Project Structure

```
my_app/
├── components/
│   └── ui/
│       ├── task_card.py
│       ├── task_card.html
│       ├── add_task_form.py
│       └── add_task_form.html
└── index.html
```

## Basic Example

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
        >
            <wa-icon slot="start" name="{% if completed %}rotate-left{% else %}check{% endif %}"></wa-icon>
            {% if completed %}Mark Incomplete{% else %}Complete{% endif %}
        </wa-button>

        <wa-button
            variant="danger"
            size="small"
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
    id: str  # Required field
```

```html
<!-- components/ui/add_task_form.html -->
<wa-card appearance="filled">
    <div slot="header">Add New Task</div>

    <form>
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

### Usage

```python
from pyjinhx import Renderer
from components.ui.task_card import TaskCard
from components.ui.add_task_form import AddTaskForm

Renderer.set_default_environment("./components")

# Render components
task_card = TaskCard(
    id="1",
    title="Learn PyJinHx",
    description="Understand how to build reusable components",
    completed=False
).render()

form = AddTaskForm(id="add-task-form").render()
```

## How templates map to WebAwesome

There is nothing WebAwesome-specific in PyJinHx — you write the custom elements directly
in a component's `.html`, and three plain-HTML conventions carry everything you need:

- **Tags** — use the element name as-is (`<wa-button>`, `<wa-card>`, `<wa-icon>`). PyJinHx
  only expands *PascalCase* tags into its own components; lowercase custom-element tags pass
  through untouched.
- **Attributes** — interpolate string/enum attrs with `{{ }}` (`variant="{{ variant }}"`),
  but emit **boolean** attrs with a guard (`{% if disabled %}disabled{% endif %}`) so a
  falsy value omits the attribute instead of setting it to `"False"`.
- **Slots** — place children into named slots with the standard `slot="..."` attribute
  (`<wa-icon slot="start" …>`); default-slot content just goes between the tags.

For the full element catalogue (variants, sizes, every attribute and slot), see the
[WebAwesome docs](https://webawesome.com/) — they are the source of truth; PyJinHx
neither adds nor constrains anything.

### One representative example

A dialog driven by a Python component shows all three conventions at once — interpolated
attrs, a guarded boolean (`open`), and `slot="header"` / `slot="footer"`:

```python
# components/ui/dialog.py
class Dialog(BaseComponent):
    id: str
    title: str
    content: str
    open: bool = False
```

```html
<!-- components/ui/dialog.html -->
<wa-dialog id="{{ id }}" {% if open %}open{% endif %}>
    <div slot="header"><h2>{{ title }}</h2></div>
    <p>{{ content }}</p>
    <div slot="footer">
        <wa-button variant="neutral" onclick="this.closest('wa-dialog').close()">Cancel</wa-button>
        <wa-button variant="brand" onclick="this.closest('wa-dialog').close()">
            <wa-icon slot="start" name="check"></wa-icon>
            Confirm
        </wa-button>
    </div>
</wa-dialog>
```
