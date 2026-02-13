# Claude Code

You can use the following skill as a [custom slash command](https://docs.anthropic.com/en/docs/claude-code/slash-commands) in Claude Code to help the AI build with PyJinHx.

## Setup

Create a file at `.claude/commands/pyjinhx.md` in your project root with the following content:

````markdown
---
name: pyjinhx
description: Build reusable, type-safe UI components with PyJinHx (Pydantic + Jinja2)
---

You are building with PyJinHx — a Python library for reusable, type-safe UI components using Pydantic + Jinja2.

## Core Concepts

Components = Python class (Pydantic BaseModel) + Jinja2 template file (same directory).

```python
from pyjinhx import BaseComponent

class Card(BaseComponent):
    id: str              # Required on all components
    title: str
    subtitle: str = ""   # Optional with default
```

Extra fields passed to a component are accepted and available in the template context (not validated).

## Template Discovery

Templates are auto-discovered from the class name. They must be in the **same directory** as the Python file.

| Class Name     | Template File                                          |
|----------------|--------------------------------------------------------|
| `Button`       | `button.html` or `button.jinja`                       |
| `ActionButton` | `action_button.html` or `action-button.html` (or `.jinja`) |

## Rendering

**Two ways to render:**

1. **Python-side** — instantiate and call `.render()`:
```python
button = Button(id="submit", text="Submit")
html = button.render()
```

2. **String-side** — PascalCase tags in HTML strings:
```python
from pyjinhx import Renderer
renderer = Renderer.get_default_renderer()
html = renderer.render('<Button id="submit" text="Submit"/>')
```

PascalCase tag resolution order:
1. Registered instance (matching ID) — reuses and updates props
2. Registered class (matching tag name) — creates new instance with Pydantic validation
3. Generic fallback — uses BaseComponent with auto-discovered template, no validation

Inner content of tags becomes the `{{ content }}` template variable.

## Templates

Templates receive all component fields as variables. Use full Jinja2 syntax. **PascalCase tags work inside templates too** — PyJinHx expands them automatically during rendering, so you can compose components declaratively:

```html
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {% if subtitle %}<p>{{ subtitle }}</p>{% endif %}
    <Button id="card-action" text="Click me"/>
</div>
```

This means any `.html` or `.jinja` template — whether a component template, a page template, or a string passed to `renderer.render()` — can contain `<PascalCase/>` tags that get resolved to components.

## Nesting

Nested components are wrapped in `NestedComponentWrapper`. Render with `{{ child }}`, access props with `{{ child.props.field }}`.

```python
class Card(BaseComponent):
    id: str
    title: str
    action: Button  # Single nested component
    items: list[Button]  # List of components
    widgets: dict[str, Button]  # Dict of components
```

```html
{{ action }}                          {# renders the nested component #}
{{ action.props.text }}               {# access nested props #}
{% for item in items %}{{ item }}{% endfor %}
{% for key, val in widgets.items() %}{{ val }}{% endfor %}
```

Lists and dicts can mix components with strings. Nesting depth is unlimited.

## Assets (JS & CSS)

Place kebab-case `.js` and/or `.css` files next to the component. They are auto-collected, deduplicated per render session, and injected at the root render — CSS as `<style>` before the HTML, JS as `<script>` after.

| Class Name     | JS File             | CSS File             |
|----------------|---------------------|----------------------|
| `Button`       | `button.js`         | `button.css`         |
| `ActionButton` | `action-button.js`  | `action-button.css`  |

Each component gets its own `<script>`/`<style>` tag (errors in one don't break others). Add extra files via the `js` and `css` fields:

```python
widget = MyWidget(id="w1", js=["path/to/extra.js"], css=["path/to/theme.css"])
```

Missing extra files emit a warning (check `pyjinhx` logger). Disable inline assets with `Renderer.set_default_inline_js(False)` / `Renderer.set_default_inline_css(False)`. Use `Finder(root).collect_javascript_files()` / `Finder(root).collect_css_files()` for static serving.

## Registry

Components auto-register on definition (classes) and instantiation (instances). Composite key: `ClassName_id` — different types can share an ID.

For web apps, isolate per-request with `Registry.request_scope()`:

```python
from pyjinhx import Registry

with Registry.request_scope():
    btn = Button(id="submit", text="Go")
    html = btn.render()
# Cleaned up automatically
```

Or use middleware for app-wide coverage:

```python
class RegistryScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        with Registry.request_scope():
            return await call_next(request)
```

## Configuration

```python
from pyjinhx import Renderer

# Set template root (string path or Jinja2 Environment)
Renderer.set_default_environment("./components")

# Or use a custom Jinja2 Environment
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("./components"))
Renderer.set_default_environment(env)
```

## Project Structure

```
my_app/
├── components/
│   └── ui/
│       ├── button.py
│       ├── button.html
│       ├── button.js          # Optional, auto-collected
│       ├── button.css         # Optional, auto-collected
│       ├── card.py
│       └── card.html
├── main.py
└── pyproject.toml
```

## Public API

```python
from pyjinhx import BaseComponent, Renderer, Registry, Finder, Parser, Tag
```

- `BaseComponent` — base class for all components
- `Renderer` — renders strings with PascalCase tags or manages environments
- `Registry` — query/clear instances and classes, `request_scope()` context manager
- `Finder` — template/asset discovery, `collect_javascript_files()`, `collect_css_files()`, `detect_root_directory()`
- `Parser` / `Tag` — HTML parsing internals (rarely needed directly)
````

## Usage

After creating the file, use the `/pyjinhx` command in Claude Code before asking it to build components. Claude will then follow PyJinHx conventions automatically — correct file placement, naming, nesting patterns, and rendering approach.
