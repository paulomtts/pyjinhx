# PyJinHx

Build reusable, type-safe UI components for template-based web apps in Python. PyJinHx combines Pydantic models with Jinja2 templates to give you template discovery, component composition, and JavaScript bundling.

- **Automatic Template Discovery**: Place templates next to component files—no manual paths
- **JavaScript Bundling**: Automatically collects and bundles `.js` files from component directories
- **Composability**: Nest components easily—works with single components, lists, and dictionaries
- **Flexible**: Use Python classes for reusable components, HTML syntax for quick page composition
- **Type Safety**: Pydantic models provide validation and IDE support

## Installation

```bash
pip install pyjinhx
```

## Example

This single example shows the full setup (Python classes + templates) and both ways to render:

- Python-side: instantiate a component class and call `.render()`.
- Template-side: render an HTML-like string with custom tags via `Renderer`.

### Step 1: Define component classes

```python
# components/ui/button.py
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"
```

```python
# components/ui/card.py
from pyjinhx import BaseComponent
from components.ui.button import Button


class Card(BaseComponent):
    id: str
    title: str
    action_button: Button
```

```python
# components/ui/page.py
from pyjinhx import BaseComponent
from components.ui.card import Card


class Page(BaseComponent):
    id: str
    title: str
    main_card: Card
```

### Step 2: Create templates (auto-discovered next to the class files)

```html
<!-- components/ui/button.html -->
<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>
```

```html
<!-- components/ui/card.html -->
<div id="{{ id }}" class="card">
  <h2>{{ title }}</h2>
  <div class="action">{{ action_button }}</div>
</div>
```

```html
<!-- components/ui/page.html -->
<main id="{{ id }}">
  <h1>{{ title }}</h1>
  {{ main_card }}
</main>
```

### Step 3A: Python-side rendering (`BaseComponent.render()`)

```python
from components.ui.button import Button
from components.ui.card import Card
from components.ui.page import Page

page = Page(
    id="home",
    title="Welcome",
    main_card=Card(
        id="hero",
        title="Get Started",
        action_button=Button(id="cta", text="Sign up", variant="primary"),
    ),
)

html = page.render()
```

### Step 3B: Template-side rendering (`Renderer(...).render(source)`)

```python
from pyjinhx import Renderer

renderer = Renderer("./components", auto_id=True)

html = renderer.render(
    """
    <Page title="Welcome">
      <Card title="Get Started">
        <Button text="Sign up" variant="primary"/>
      </Card>
    </Page>
    """
)
```

Template-side rendering supports:

- Type safety for registered classes: if `Button(BaseComponent)` exists, its fields are validated when `<Button .../>` is instantiated.
- Generic tags: if there is no registered class, a generic `BaseComponent` is used as long as the template file can be found.

## JavaScript & extra assets

- Component-local JS: if a component class `MyWidget` has a sibling file `my-widget.js`, it is auto-collected and injected once at the root render level.
- Extra JS: pass `js=[...]` with file paths; missing files are ignored.
- Extra HTML files: pass `html=[...]` with file paths; they are rendered and exposed in the template context by filename stem (e.g. `extra_content.html` → `extra_content.html` wrapper). Missing files raise `FileNotFoundError`.

## FastAPI + HTMX example

### Component class

```python
# components/ui/button.py
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
```

### Component template (with HTMX)

```html
<!-- components/ui/button.html -->
<button
  id="{{ id }}"
  hx-post="/clicked"
  hx-vals='{"button_id": "{{ id }}"}'
  hx-target="#click-result"
  hx-swap="innerHTML"
>
  {{ text }}
</button>
```

### FastAPI app (two routes)

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from components.ui.button import Button

app = FastAPI()


@app.get("/button", response_class=HTMLResponse)
def button() -> str:
    return (
        Button(id="save-btn", text="Click me").render()
        + '<div id="click-result"></div>'
    )


@app.post("/clicked", response_class=HTMLResponse)
def clicked(button_id: str = "unknown") -> str:
    return f"Clicked: {button_id}"
```
