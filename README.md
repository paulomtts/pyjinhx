# PyJinHx

Declare reusable, type-safe UI components for template-based web apps in Python. PyJinHx combines Pydantic models with Jinja2 templates to give you automatic template discovery, nested composition, and JavaScript automatic collection—all without manual wiring.

## Installation

```bash
pip install pyjinhx
```

## Core Capabilities

- **Automatic Template Discovery**: Place an HTML template next to your component class with a matching name (e.g., `button.html` for `Button`)
- **Generic Components**: Create components directly from `BaseComponent` with custom properties and HTML templates
- **Global Component Registry**: All components register by `id` and are accessible in any template via `{{ component_id }}`
- **Nested Components**: Pass components as fields—works with single components, lists, and dictionaries
- **Property Access**: Access nested component properties via `.props` (e.g., `{{ nested.props.text }}`)
- **JavaScript Automatic Collection**: Automatically collects `.js` files next to templates and bundles them into a single `<script>` tag
- **Extra HTML Templates**: Include additional HTML files via the `html` field

## Example

```python
# components/ui/button.py
from pyjinhx import BaseComponent

class Button(BaseComponent):
    id: str
    text: str
```

```html
<!-- components/ui/button.html -->
<button id="{{ id }}">{{ text }}</button>
```

```python
# components/ui/card.py
from pyjinhx import BaseComponent
from components.ui.button import Button

class Card(BaseComponent):
    id: str
    title: str
    action_button: Button
    menu_items: list[Button]
```

```html
<!-- components/ui/card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <div class="action">
        <p>Action: {{ action_button.props.text }}</p>
        {{ action_button.html }}
    </div>
    <ul class="menu">
        {% for item in menu_items %}
        <li>
            <span>Item: {{ item.props.text }}</span>
            {{ item.html }}
        </li>
        {% endfor %}
    </ul>
</div>
```

```python
# Usage
from components.ui.card import Card
from components.ui.button import Button

action_btn = Button(id="submit-btn", text="Submit")
menu_buttons = [
    Button(id="menu-1", text="Home"),
    Button(id="menu-2", text="About"),
    Button(id="menu-3", text="Contact")
]

card = Card(
    id="form-card",
    title="User Form",
    action_button=action_btn,
    menu_items=menu_buttons
)
html = card.render()
```

```html
<!-- Rendered output -->
<div id="form-card" class="card">
    <h2>User Form</h2>
    <div class="action">
        <p>Action: Submit</p>
        <button id="submit-btn">Submit</button>
    </div>
    <ul class="menu">
        <li>
            <span>Item: Home</span>
            <button id="menu-1">Home</button>
        </li>
        <li>
            <span>Item: About</span>
            <button id="menu-2">About</button>
        </li>
        <li>
            <span>Item: Contact</span>
            <button id="menu-3">Contact</button>
        </li>
    </ul>
</div>
```

## Generic Components

You can create components directly from `BaseComponent` without defining a subclass. This is useful for one-off components or when you want to use existing HTML templates with dynamic properties.

When you instantiate `BaseComponent` directly, it will use the HTML files specified in the `html` property as the template source (since there's no corresponding class file to discover a template from).

```python
from pyjinhx import BaseComponent

# Create a generic component with custom properties
component = BaseComponent(
    id="generic-card",
    title="Welcome",
    description="This is a generic component",
    html=["templates/card.html"]
)

html = component.render()
```

```html
<!-- templates/card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
</div>
```

```html
<!-- Rendered output -->
<div id="generic-card" class="card">
    <h2>Welcome</h2>
    <p>This is a generic component</p>
</div>
```

You can also combine multiple HTML files:

```python
component = BaseComponent(
    id="composite",
    title="Composite Component",
    html=["templates/header.html", "templates/content.html", "templates/footer.html"]
)
```

The files will be concatenated in order and rendered as a single template. All extra properties you pass (like `title`, `description`, etc.) are automatically available in the template context thanks to Pydantic's `extra='allow'` configuration.
