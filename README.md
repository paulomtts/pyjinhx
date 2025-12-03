# PyJinx

Server-side UI components for Python using Pydantic and Jinja2 templates. Build reusable, type-safe components that automatically discover templates and handle nested rendering.

## Installation

```bash
pip install pyjinx
```

## Quick Start

### 1. Set up the template engine

```python
from jinja2 import Environment, FileSystemLoader
from pyjinx import BaseComponent

env = Environment(loader=FileSystemLoader("templates"))
BaseComponent.set_engine(env)
```

### 2. Create a component

Create a template file at `templates/ui/button.html`:

```html
<button id="{{ id }}" class="btn">{{ text }}</button>
```

Define the component class:

```python
from pyjinx import BaseComponent

class Button(BaseComponent):
    id: str
    text: str
```

### 3. Use the component

```python
button = Button(id="submit-btn", text="Click Me")
```

In Jinja2 templates, components render automatically:

```html
{{ submit-btn }}
```

## Features

### Automatic Template Discovery

Components automatically find their templates based on class name and location. A `Button` class in `components/` will look for `components/ui/button.html`.

### Nested Components

Components can contain other components:

```python
class Card(BaseComponent):
    id: str
    title: str
    content: Button  # Nested component

card = Card(
    id="card-1",
    title="My Card",
    content=Button(id="btn-1", text="Action")
)
```

Nested components are automatically rendered and available in the template context by their ID.

### JavaScript Integration

Place a JavaScript file next to your component (e.g., `button.js`), and it will be automatically inlined in the rendered HTML:

```javascript
// button.js
document.getElementById('{{ id }}').addEventListener('click', () => {
    console.log('Button clicked!');
});
```

### FastAPI Integration

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pyjinx import BaseComponent

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    button = Button(id="home-btn", text="Home")
    return button.render()
```

### HTMX Compatibility

Components work seamlessly with HTMX for dynamic updates:

```html
<!-- card.html -->
<div id="{{ id }}" hx-get="/api/card/{{ id }}" hx-trigger="refresh">
    {{ title }}
    {{ content }}
</div>
```

```python
@app.get("/api/card/{card_id}", response_class=HTMLResponse)
async def get_card(card_id: str):
    card = Card(id=card_id, title="Dynamic Card", content=...)
    return card.render()
```

## Component Fields

- `id` (required): Unique identifier for the component
- `js` (optional): Custom JavaScript file name
- `html` (optional): List of additional HTML template files to include

## Component Registry

All components are automatically registered and available in the global template context:

```python
from pyjinx import Registry

# Access all registered components
components = Registry.get()

# Clear the registry
Registry.clear()
```

We recomend you clear the registry before each request is processed.

## Requirements

- Python >= 3.13
- Jinja2 >= 3.1.6
- Pydantic >= 2.12.5
- MarkupSafe >= 3.0.3

## License

MIT

