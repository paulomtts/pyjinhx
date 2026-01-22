# Rendering

PyJinHx has **two ways to render components**:

- Call **`.render()` on a `BaseComponent` instance** you created in Python
- Use a **`Renderer`** to render an HTML-like string containing **PascalCase component tags**

## 1) Render a component instance with `.render()`

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

## 2) Render an HTML-like string with `Renderer`

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
