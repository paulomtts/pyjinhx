# PyJinHx

Build reusable, type-safe UI components for template-based web apps in Python. PyJinHx combines Pydantic models with Jinja2 templates to give you template discovery, component composition, and JavaScript bundling.

## Installation

```bash
pip install pyjinhx
```

## Core ideas

You can use PyJinHx in two ways, and mix them:

- Python-side: render a **typed Python component instance** (`BaseComponent.render()`).
- Template-side: render **HTML-like source** with PascalCase custom tags (`Renderer(...).render(source)`).

## Python-to-HTML Example

Start here if you want a typed component library.

### Step 1: Define Component Classes

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
    menu_items: list[Button]
```

### Step 2: Create Templates

```html
<!-- components/ui/button.html (auto-discovered) -->
<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>
```

```html
<!-- components/ui/card.html (auto-discovered) -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <div class="action">
        <p>Button: {{ action_button.props.text }}</p>
        {{ action_button }}
    </div>
    <ul class="menu">
        {% for item in menu_items %}
        <li>{{ item }}</li>
        {% endfor %}
    </ul>
</div>
```

### Step 3: Use in Python

```python
from components.ui.card import Card
from components.ui.button import Button

card = Card(
    id="form-card",
    title="User Form",
    action_button=Button(id="submit", text="Submit", variant="primary"),
    menu_items=[
        Button(id="home", text="Home"),
        Button(id="about", text="About")
    ]
)
html = card.render()
```

## HTML-like syntax (custom tags)

Start here if you prefer composing pages with an HTML-like string.

```html
<!-- templates/card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {{ content }}
</div>
```

```html
<!-- templates/button.html -->
<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>
```

```python
from jinja2 import Environment, FileSystemLoader
from pyjinhx import Renderer

renderer = Renderer(Environment(loader=FileSystemLoader("./templates")), auto_id=True)
html = renderer.render('''
    <Card title="Welcome">
        <Button text="Get Started" variant="primary"/>
        <Button text="Learn More" variant="secondary"/>
    </Card>
''')
```

This mode supports:

- Registered classes: if `Button(BaseComponent)` exists, its Pydantic fields are enforced when `<Button .../>` is instantiated.
- Generic tags: if there is no registered class, a generic `BaseComponent` is used as long as the template file can be found.

## Use custom tags inside component templates

`BaseComponent.render()` expands `<PascalCase />` tags found inside a component template, so component templates can compose other components directly:

```html
<!-- components/ui/page.html -->
<div id="{{ id }}">
  <Button id="save" text="Save"/>
</div>
```

## JavaScript & extra assets

- Component-local JS: if a component class `MyWidget` has a sibling file `my-widget.js`, it is auto-collected and injected once at the root render.
- Extra JS: pass `js=[...]` with file paths; missing files are ignored.
- Extra HTML files: pass `html=[...]` with file paths; they are rendered and exposed in the template context by filename stem (e.g. `extra_content.html` → `extra_content.html` wrapper). Missing files raise `FileNotFoundError`.

## Configuration

- Default environment: `Renderer.get_default_renderer()` auto-detects a project root and uses `FileSystemLoader(root)`.
- Override: call `Renderer.set_default_environment(Environment(loader=FileSystemLoader(...)))` for explicit control (tests do this).

## Key Benefits

- **Type Safety**: Pydantic models provide validation and IDE support
- **Composability**: Nest components easily—works with single components, lists, and dictionaries
- **Automatic Template Discovery**: Place templates next to component files—no manual paths
- **JavaScript Bundling**: Automatically collects and bundles `.js` files from component directories
- **Flexible**: Use Python classes for reusable components, HTML syntax for quick page composition
