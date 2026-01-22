# PyJinHx

Build reusable, type-safe UI components for template-based web apps in Python.

PyJinHx combines **Pydantic models** with **Jinja2 templates** to give you template discovery, component composition, and JavaScript bundling.

## Features

- **Automatic Template Discovery** - Place templates next to component files, no manual paths needed
- **Composability** - Nest components easily with single components, lists, and dictionaries
- **JavaScript Bundling** - Automatically collects and bundles `.js` files from component directories
- **Type Safety** - Pydantic models provide validation and IDE support

## Two Ways to Render

PyJinHx offers two complementary approaches:

=== "Python-side"

    Instantiate components in Python and call `.render()`:

    ```python
    from components.ui.button import Button

    button = Button(id="submit", text="Submit", variant="primary")
    html = button.render()
    ```

=== "Template-side"

    Use HTML-like syntax with the `Renderer`:

    ```python
    from pyjinhx import Renderer

    renderer = Renderer("./components")
    html = renderer.render('<Button text="Submit" variant="primary"/>')
    ```

## Quick Example

```python
from pyjinhx import BaseComponent

class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"
```

```html
<!-- button.html (next to button.py) -->
<button id="{{ id }}" class="btn btn-{{ variant }}">
    {{ text }}
</button>
```

```python
button = Button(id="cta", text="Click me", variant="primary")
print(button.render())
# <button id="cta" class="btn btn-primary">Click me</button>
```

## Next Steps

- [Installation](getting-started/installation.md) - Install PyJinHx
- [Quick Start](getting-started/quickstart.md) - Build your first component
- [Guide](guide/components.md) - Learn all the features
