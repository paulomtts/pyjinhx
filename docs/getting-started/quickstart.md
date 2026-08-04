# Quick Start

This guide walks you through creating your first PyJinHx component.

## Project Structure

A typical PyJinHx components folder looks like this:

```
my_project/
└── components/
    └── ui/
        ├── button.py      # Component class
        └── button.pjx     # Component template
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
- Has an `id` field — auto-generated (`pjx-<n>`) if omitted; redeclare `id: str` to require one
- Can have additional fields with optional defaults

## Step 2: Create the Template

Create `components/ui/button.pjx` (same directory as the class):

```html
<button id="{{ id }}" class="btn btn-{{ variant }}">
    {{ text }}
</button>
```

!!! info "Template Discovery"
    PyJinHx finds a component's own template by converting the class name to
    snake_case and appending `.pjx`, in the same directory as the class:
    `Button` → `button.pjx`, `ActionButton` → `action_button.pjx`. This is
    separate from how PascalCase tags *referenced inside* a template body are
    resolved — see [PascalCase tags](../guide/tags.md) for that lookup.

## Step 3: Render the Component

Create `main.py`:

```python
from pyjinhx import RenderSession
from components.ui.button import Button

# A RenderSession carries the Jinja environment. It takes no arguments —
# each component finds its own template next to its class.
session = RenderSession()

# Create and render
button = Button(id="submit-btn", text="Submit", variant="primary")

html = button.render(session)
print(html)
```

!!! tip "The session is optional"
    `button.render()` with no argument uses the session bound by the active
    `request_scope()`, or builds a fresh one if there is no scope. Pass a session
    explicitly only when you want several renders to share one — for example to
    accumulate their assets together.

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
