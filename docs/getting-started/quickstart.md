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

## Step 3: Serve It

Create `main.py`:

```python
from fastapi import FastAPI

from components.ui.button import Button
from pyjinhx import setup

app = FastAPI()
setup(app, components_root="components")


@app.get("/")
def index():
    return Button(id="submit-btn", text="Submit", variant="primary")
```

Run it with `uvicorn main:app --reload` and open <http://127.0.0.1:8000/>:

```html
<button id="submit-btn" class="btn btn-primary">
    Submit
</button>
```

Two things to take from this, because they hold for every route you will write:

- **Routes return components; they do not render them.** Returning the instance
  is what hands the request to pyjinhx's response composer, which is where
  everything past "one component's markup" happens — the client runtime is
  injected on a cold page render, co-located CSS and JS ride along, and
  [reactive out-of-band swaps](../reactivity.md) are attached. Call `.render()`
  yourself and you get the markup alone.
- **`setup()` runs once, before your routes.** It registers your components so
  [PascalCase tags](../guide/tags.md) resolve, and installs the middleware that
  opens a request scope. It can only register classes that are already imported
  when it runs, so import your components above it.

!!! warning "`components_root` is relative to the working directory"
    `"components"` resolves against wherever you start the process, not against
    `main.py`. Run `uvicorn` from the project root, or pass an absolute path
    (`Path(__file__).parent / "components"`) if you need it to work from anywhere.

!!! tip "No web framework? Render to a string"
    Components work without a server — see
    [Usage tiers](../guide/usage-tiers.md). Skip `setup()` and call `render()`:

    ```python
    from pyjinhx import render
    from components.ui.button import Button

    print(render(Button(id="submit-btn", text="Submit", variant="primary")))
    ```

    This is the whole standalone surface. You will not need `RenderSession` for
    it — one is created for you.

## What's Next?

- **[Build an App](build-an-app.md)** — full step-by-step tutorial with **Why?** panels (start here for a real app)
- [Creating Components](../guide/components.md) - Fields, validation, and templates
- [Nesting Components](../guide/nesting.md) - Compose components together
- [Reactivity](../reactivity.md) - Dependency-aware HTMX updates
