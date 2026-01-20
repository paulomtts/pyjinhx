# Renderer

The rendering engine for HTML-like component syntax.

## Overview

`Renderer` parses HTML-like strings containing PascalCase component tags and renders them to HTML.

```python
from pyjinhx import Renderer

renderer = Renderer.get_default_renderer()
html = renderer.render('<Button text="Click me"/>')
```

## API Reference

::: pyjinhx.Renderer
    options:
      members:
        - __init__
        - render
        - environment
        - new_session
        - get_default_renderer
        - get_default_environment
        - set_default_environment
        - peek_default_environment
      show_root_heading: true
      heading_level: 3

## RenderSession

::: pyjinhx.renderer.RenderSession
    options:
      show_root_heading: true
      heading_level: 3

## Usage Examples

### Default Renderer

```python
from pyjinhx import Renderer

# Auto-detects project root
renderer = Renderer.get_default_renderer()
html = renderer.render('<Header title="My Site"/>')
```

### Custom Template Path

```python
Renderer.set_default_environment("./components")
renderer = Renderer.get_default_renderer()
```

### With Jinja Environment

```python
from jinja2 import Environment, FileSystemLoader
from pyjinhx import Renderer

env = Environment(loader=FileSystemLoader("./templates"))
renderer = Renderer(env, auto_id=True)
```

### Disabling Auto-ID

```python
renderer = Renderer.get_default_renderer(auto_id=False)

# Must provide explicit IDs
html = renderer.render('<Button id="my-btn" text="Click"/>')
```

### Nested Components

```python
html = renderer.render("""
    <Page title="Home">
        <Card title="Welcome">
            <Button text="Get Started"/>
        </Card>
    </Page>
""")
```

### Mixed Content

```python
html = renderer.render("""
    <Panel>
        Some text before
        <Button text="Action"/>
        Some text after
    </Panel>
""")
```

## How It Works

1. **Parsing**: The renderer uses an HTML parser to identify PascalCase tags
2. **Class Lookup**: For each tag, it checks if a `BaseComponent` subclass is registered
3. **Instantiation**: Creates component instances with attributes as fields
4. **Rendering**: Calls `_render()` on each component recursively
5. **Script Injection**: Collects JavaScript and injects it at the root level

## Tag Resolution

| Tag | Registered Class? | Result |
|-----|-------------------|--------|
| `<Button text="X"/>` | Yes (`Button`) | Uses `Button` class with validation |
| `<Custom attr="Y"/>` | No | Uses generic `BaseComponent` with `custom.html` |
| `<div class="x">` | N/A (lowercase) | Passed through unchanged |
