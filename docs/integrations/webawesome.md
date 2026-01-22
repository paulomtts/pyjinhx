# WebAwesome

PyJinHx integrates seamlessly with [WebAwesome](https://webawesome.com/) - a comprehensive web components library that provides 50+ customizable UI components built on web standards.

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
    pass
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

form = AddTaskForm().render()
```

## WebAwesome Components in Templates

### Using Icons

WebAwesome icons can be used with the `wa-icon` component:

```html
<!-- components/ui/button.html -->
<wa-button variant="brand">
    <wa-icon slot="start" name="check"></wa-icon>
    Submit
</wa-button>
```

### Card Variants

WebAwesome cards support different appearances:

```html
<!-- components/ui/card.html -->
<wa-card appearance="outlined">
    <div slot="header">Outlined Card</div>
    <p>Content here</p>
</wa-card>

<wa-card appearance="filled">
    <div slot="header">Filled Card</div>
    <p>Content here</p>
</wa-card>

<wa-card appearance="elevated">
    <div slot="header">Elevated Card</div>
    <p>Content here</p>
</wa-card>
```

### Input Components

WebAwesome provides styled input components:

```html
<!-- components/ui/form.html -->
<wa-input
    name="email"
    label="Email Address"
    type="email"
    required
    placeholder="Enter your email"
></wa-input>

<wa-textarea
    name="message"
    label="Message"
    rows="4"
    placeholder="Enter your message"
></wa-textarea>
```

### Button Variants

WebAwesome buttons support multiple variants:

```html
<!-- components/ui/button.html -->
<wa-button variant="brand">Brand</wa-button>
<wa-button variant="success">Success</wa-button>
<wa-button variant="danger">Danger</wa-button>
<wa-button variant="neutral">Neutral</wa-button>
<wa-button variant="warning">Warning</wa-button>
```

### Conditional Rendering

Use Jinja conditionals to control WebAwesome component attributes:

```html
<!-- components/ui/alert.html -->
<wa-alert
    variant="{% if level == 'error' %}danger{% elif level == 'warning' %}warning{% else %}info{% endif %}"
    open
>
    {{ message }}
</wa-alert>
```

## Tips

### Component Slots

WebAwesome components use slots for flexible content placement:

```html
<!-- components/ui/button.html -->
<wa-button>
    <wa-icon slot="start" name="save"></wa-icon>
    Save
    <wa-icon slot="end" name="arrow-right"></wa-icon>
</wa-button>
```

### Styling

WebAwesome components can be styled with CSS custom properties:

```html
<!-- components/ui/card.html -->
<wa-card
    style="--wa-card-padding: 2rem; --wa-card-border-radius: 12px;"
>
    <div slot="header">Custom Styled Card</div>
    <p>Content</p>
</wa-card>
```

### Component Composition

Combine multiple WebAwesome components in your PyJinHx templates:

```html
<!-- components/ui/dialog.html -->
<wa-dialog id="{{ id }}" open="{{ open }}">
    <div slot="header">
        <h2>{{ title }}</h2>
    </div>
    <p>{{ content }}</p>
    <div slot="footer">
        <wa-button variant="neutral" onclick="this.closest('wa-dialog').close()">
            Cancel
        </wa-button>
        <wa-button variant="brand" onclick="this.closest('wa-dialog').close()">
            Confirm
        </wa-button>
    </div>
</wa-dialog>
```

### Dynamic Attributes

Pass WebAwesome component attributes from your Python component:

```python
# components/ui/button.py
class Button(BaseComponent):
    id: str
    text: str
    variant: str = "brand"
    size: str = "medium"
    disabled: bool = False
```

```html
<!-- components/ui/button.html -->
<wa-button
    id="{{ id }}"
    variant="{{ variant }}"
    size="{{ size }}"
    {% if disabled %}disabled{% endif %}
>
    {{ text }}
</wa-button>
```
