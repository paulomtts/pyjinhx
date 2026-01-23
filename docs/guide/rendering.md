# Rendering

PyJinHx has **two ways to render components**:

- Call **`.render()` on a `BaseComponent` instance** you created in Python
- Use a **`Renderer`** to render an HTML-like string containing **PascalCase component tags**

## Render from a component instance

Use this when you want **typed, validated** component instances in Python.

```python
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str


button = Button(id="submit", text="Submit")
html = button.render()
```

This renders the component using the **template adjacent to the component class file** (matched from the class name, e.g. `Button` → `button.html` / `button.jinja`).

## Render from string

Use this when you want to write **declarative markup** and let PyJinHx expand components.

```python
from pyjinhx import Renderer

renderer = Renderer.get_default_renderer()
html = renderer.render('<Button text="Click me"/>')
```

!!! tip "Configuring the Renderer"
    See the [Configuration](configuration.md) page for details on setting up template paths and Jinja environments.

### PascalCase tags become components

When rendering a string, the renderer treats **PascalCase tags** as components:

```python
html = renderer.render("""
    <Header title="My Site"/>
    <Nav>Home | About | Contact</Nav>
    <Footer>Copyright 2024</Footer>
""")
```

### Attributes

Attributes work like HTML attributes and become template context variables:

```python
html = renderer.render('''
    <Input
        type="email"
        name="user_email"
        placeholder="Enter your email"
        required="true"
    />
''')
```

### Component resolution

When rendering a PascalCase tag, the renderer resolves components in this order:

1. **Registered instance** — If the tag's `id` matches an existing registered instance, that instance is used and updated with the tag's attributes
2. **Registered class** — If the tag name matches a registered `BaseComponent` subclass, a new instance is created
3. **Generic fallback** — Uses `BaseComponent` with the auto-discovered template

See [PascalCase Components](tags.md#component-resolution-priority) for details on instance lookup and type validation.
