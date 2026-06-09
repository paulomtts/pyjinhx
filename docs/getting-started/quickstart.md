# Quick Start

This guide walks you through creating your first PyJinHx component.

## Project Structure

A typical PyJinHx components folder looks like this:

```
my_project/
└── components/
    └── ui/
        ├── button.py      # Component class
        └── button.html    # Component template
```

## Step 1: Create a Component Class

Create `components/ui/button.py`:

```python
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"
```

Every component:

- Inherits from `BaseComponent`
- Has a required `id` field (unique identifier)
- Can have additional fields with optional defaults

## Step 2: Create the Template

Create `components/ui/button.html` (same directory as the class):

```html
<button id="{{ id }}" class="btn btn-{{ variant }}">
    {{ text }}
</button>
```

!!! info "Template Discovery"
    PyJinHx automatically finds templates by converting the class name to snake_case.
    `Button` → `button.html`, `ActionButton` → `action_button.html`

## Step 3: Render the Component

Create `main.py`:

```python
from pyjinhx import Renderer

# Set the template search path
Renderer.set_default_environment("./components")

# Import components after setting the default environment so template
# discovery is rooted at the path above.
from components.ui.button import Button

# Create and render
button = Button(
    id="submit-btn",
    text="Submit",
    variant="primary"
)

html = button.render()
print(html)
```

Output:

```html
<button id="submit-btn" class="btn btn-primary">
    Submit
</button>
```

## What's Next?

- **[Build an App](build-an-app.md)** — full step-by-step tutorial with **Why?** panels (start here for a real app)
- [Creating Components](../guide/components.md) - Fields, validation, and templates
- [Nesting Components](../guide/nesting.md) - Compose components together
- [Reactivity](../reactivity.md) - Dependency-aware HTMX updates
