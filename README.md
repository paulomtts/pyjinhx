# PyJinHx

[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Jinja](https://img.shields.io/badge/Jinja-B41717?logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/)
[![HTMX](https://img.shields.io/badge/HTMX-3366CC?logo=htmx&logoColor=white)](https://htmx.org/)

Type-safe UI components for Python web apps. A component is a Pydantic model plus a Jinja template sitting next to it — nest them with PascalCase tags, and co-located JS/CSS is collected automatically at render.

```bash
pip install pyjinhx
```

## Example

A `Card` that renders a `Button` — the tag's attributes become validated Pydantic fields:

```python
# components/button.py
from pyjinhx import BaseComponent

class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"
```

```html
<!-- components/button.html -->
<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>
```

```html
<!-- components/card.html -->
<div id="{{ id }}" class="card">
  <h2>{{ title }}</h2>
  <Button id="cta" text="{{ button_text }}" variant="primary"/>
</div>
```

```python
# components/card.py
from pyjinhx import BaseComponent, Renderer

class Card(BaseComponent):
    id: str
    title: str
    button_text: str = "Sign up"

Renderer.set_default_environment("./components")
html = Card(id="hero", title="Get Started").render()
```

Drop a `button.css` or `card.js` next to the component and it's included once, automatically.

## Reactivity (HTMX)

Components declare what state they depend on. Return one component from a mutation route — every other mounted region that reacts to the same keys updates via out-of-band swaps, no manual wiring:

```python
from pyjinhx import ReactiveComponent, MutationKey, mutates, setup

class Keys(MutationKey):
    TODOS = "todos"

class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())

@mutates(Keys.TODOS)
def toggle_all():
    db.toggle_all()

setup(app)  # FastAPI: lifespan + middleware, done

@app.post("/todos/toggle")
def toggle():
    toggle_all()
    return Counter.render()  # other regions reacting to TODOS update too
```

## Single-file components

Combine the Python class and the Jinja template in a single `.pjx` file — no build step:

```jinja
{# python
from pyjinhx import BaseComponent

class Badge(BaseComponent):
    label: str
    count: int = 0
#}
<span class="badge">{{ label }} ({{ count }})</span>
```

```python
from app.components.badge import Badge

html = Badge(label="inbox", count=3).render()
```

See [Single-file components](docs/single-file-components.md) for the full format, the `__pjx_component__` escape hatch, and the pyright stub workflow.

## Learn more

- [Usage tiers](docs/guide/usage-tiers.md) — adopt only the layers you need
- [Components](docs/guide/components.md) · [PascalCase tags](docs/guide/tags.md) · [Assets](docs/guide/assets.md)
- [Reactivity guide](docs/reactivity.md) · [full todo example](examples/reactive_todo/)
- [Built-in UI kit](docs/guide/builtins.md)
