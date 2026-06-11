# Creating Components

Components are the building blocks of your UI. Each component is a Python class paired with a Jinja2 template.

## Basic Component

A component has two parts:

### 1. Python Class

```python
from pyjinhx import BaseComponent


class Card(BaseComponent):
    id: str              # Required - unique identifier
    title: str           # Required field
    subtitle: str = ""   # Optional with default
```

`BaseComponent` also provides `js` and `css` fields (lists of extra asset paths) — see [Asset Collection](assets.md).

### 2. HTML Template

PyJinHX uses **Jinja2** templates for its components:

```html
<!-- card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {% if subtitle %}
        <p class="subtitle">{{ subtitle }}</p>
    {% endif %}
</div>
```

!!! tip "You can use PascalCase components inside templates"
    You can even use PascalCase components as custom tags **inside your component templates**. This lets you compose components by nesting, like `<Button .../>` or `<UserCard>...</UserCard>`, directly within other templates. PyJinHx will automatically discover and render them as components.


## The `id` Field

`id` is **auto-generated** (`px-<n>`) when omitted. Pass an explicit id for stable hooks (CSS selectors, htmx targets, reactive OOB targeting):

```python
button = Button(id="submit", text="Submit")  # explicit — stable hook
button = Button(text="Submit")               # auto-generated px-<n>
```

!!! tip "Using your own id scheme"
    Override `id` with a `default_factory` to apply your own generation strategy — for example a UUID:

    ```python
    import uuid
    from pyjinhx import BaseComponent
    from pydantic import Field

    class MyComponent(BaseComponent):
        id: str = Field(default_factory=lambda: str(uuid.uuid4()))
        # ... other fields ...
    ```

    A subclass that redeclares `id: str` **without** a default makes it required at instantiation time.


!!! tip "Auto-generated IDs apply to PascalCase tags only"
    `auto_id` does **not** affect plain Python instances — omitting `id` on `BaseComponent(...)` falls back to the built-in `px-<n>` counter. The `Renderer`'s `auto_id=True` only generates an `id` when a PascalCase `<Tag/>` is expanded in a template without one (see [PascalCase Tags](tags.md)). Separately, `ReactiveComponent` (not `BaseComponent`) defaults its `id` to the kebab-cased class name (e.g. `TodoCounter` → `"todo-counter"`).


## Template Discovery

Templates are automatically discovered based on the class name:

| Class Name | Template File |
|------------|---------------|
| `Button` | `button.html` or `button.jinja` |
| `ActionButton` | `action_button.html`, `action-button.html`, or `.jinja` variants |
| `UserCard` | `user_card.html`, `user-card.html`, or `.jinja` variants |

!!! warning "Template Location Requirement"
    Templates must be in the same directory as the Python class file.

A subclass with no adjacent template inherits the nearest ancestor's template and class
assets, each resolved independently (first found per kind walking the MRO). At most one
component base per class — a definition-time `TypeError` is raised if two component bases
appear in `__bases__`. Framework bases (`ReactiveComponent`) don't count toward that
limit, so `class LiveBadge(ReactiveComponent, Badge, react={...})` is valid.

## Extra Fields

A plain Pydantic `BaseModel` rejects unknown fields with a `ValidationError`. With `BaseComponent`, **extra fields are accepted and available in the template context**. This allows you to pass dictionaries or data objects with additional fields without raising validation errors.

```python
from pyjinhx import BaseComponent

class Example(BaseComponent):
    foo: int

ex = Example(foo=1, bar=2)  # No error! 'bar' is just ignored
```