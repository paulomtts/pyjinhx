# PyJinHx

Declare reusable, type-safe UI components for template-based web apps in Python. PyJinHx combines Pydantic models with Jinja2 templates to give you automatic template discovery, nested composition, and JavaScript integration—all without manual wiring.

## Installation

```bash
pip install pyjinhx
```

## Core Capabilities

**Automatic Template Discovery**
- Define a component class and place an HTML template in the same directory with a matching name
- PyJinHx automatically finds `components/ui/button.html` for a `Button` class in `components/ui/button.py`
- No manual template path configuration needed

**Global Component Registry**
- Every component automatically registers itself by its `id` when instantiated
- All registered components are available in any template context by using its id: `{{ component_id }}`
- Manage the registry state as you wish, have it be request-scoped - or not!

**Nested Components**
- Pass components as fields to other components
- Nested components are wrapped in an `Object` that provides:
  - `.html` - the rendered HTML string for simple inclusion
  - `.properties` - access to the component instance and its properties
- Works with single components, lists, and dictionaries

**JavaScript Integration**
- Place a `.js` file next to your component template (e.g., `button.js` next to `button.html`)
- JavaScript is automatically collected during rendering and bundled into a single `<script>` tag at the root level
- Specify a custom JS filename with the `js` field

**Extra HTML Templates**
- Include additional HTML files via the `html` field (list of file paths)
- Each extra template is rendered and added to the context by its filename
- Access rendered content via `{{ filename.html }}` in your main template

## Technical Details

- **Type Safety**: Pydantic models provide validation and IDE support
- **Template Engine**: Jinja2 with FileSystemLoader (customizable)
- **Rendering**: Components render via `render()` or automatically via `__html__()`
- **Context Management**: Thread-safe context variables for registry and script collection
- **Required Fields**: `id` (unique identifier)
- **Optional Fields**: `js` (custom JS filename), `html` (list of extra HTML files)

## Complete Example

```python
# components/ui/button.py
from pyjinhx import BaseComponent

class Button(BaseComponent):
    id: str
    text: str
    variant: str = "primary"
```

```html
<!-- components/ui/button.html -->
<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>
```

```javascript
// components/ui/button.js
console.log('Button {{ id }} initialized');
```

```python
# components/ui/card.py
from pyjinhx import BaseComponent
from components.ui.button import Button

class Card(BaseComponent):
    id: str
    title: str
    content: Button
```

```html
<!-- components/ui/card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <div class="card-body">
        {{ content.html }}
    </div>
    <div class="card-footer">
        {{ footer.html }}
    </div>
</div>
```

```html
<!-- components/ui/footer.html -->
<p class="footer-text">© 2024 My App</p>
```

```python
# Usage
from components.ui.card import Card
from components.ui.button import Button

action_btn = Button(id="action-1", text="Submit", variant="success")

card = Card(
    id="form-card",
    title="User Form",
    content=action_btn,
    html=["components/ui/footer.html"]
)

# Render the component
html = card.render()
# The card template can access:
# - Nested components via .html (e.g., {{ content.html }})
# - Component properties via .properties (e.g., {{ content.properties.text }})
# - Extra HTML templates via .html (e.g., {{ footer.html }})
# - Any registered component by ID (e.g., {{ action-1 }})
# - All JavaScript files bundled at the end
```

```html
<!-- Render any component by ID in any template -->
<!-- page.html -->
<div>{{ form-card }}</div>
```

This example demonstrates nested components, extra HTML templates, the global registry, Object wrapping with `.html` and `.properties`, automatic template discovery, JavaScript bundling, and rendering components by ID.
