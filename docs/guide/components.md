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

### 2. HTML Template

```html
<!-- card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {% if subtitle %}
        <p class="subtitle">{{ subtitle }}</p>
    {% endif %}
</div>
```

## Field Types

Components support all Pydantic field types:

```python
from pyjinhx import BaseComponent


class UserProfile(BaseComponent):
    id: str
    name: str
    age: int
    email: str | None = None
    tags: list[str] = []
    is_active: bool = True
```

## Validation

Pydantic validation works out of the box:

```python
from pydantic import Field, field_validator
from pyjinhx import BaseComponent


class Rating(BaseComponent):
    id: str
    score: int = Field(ge=1, le=5)  # Must be 1-5

    @field_validator("score")
    @classmethod
    def validate_score(cls, v):
        if v < 1 or v > 5:
            raise ValueError("Score must be between 1 and 5")
        return v
```

```python
rating = Rating(id="r1", score=3)  # OK
rating = Rating(id="r2", score=10) # Raises ValidationError
```

## Template Discovery

Templates are automatically discovered based on the class name:

| Class Name | Template File |
|------------|---------------|
| `Button` | `button.html` or `button.jinja` |
| `ActionButton` | `action_button.html` or `action_button.jinja` |
| `UserCard` | `user_card.html` or `user_card.jinja` |

Templates must be in the same directory as the Python class file.

## Rendering

### Using `.render()`

```python
card = Card(id="main", title="Welcome")
html = card.render()
```

### Using in Jinja Templates

Components implement `__html__`, so you can use them directly:

```html
<!-- In a parent template -->
{{ card }}

<!-- Equivalent to -->
{{ card.render() }}
```

## Extra Fields

Components allow extra fields via Pydantic's `extra="allow"`:

```python
button = Button(
    id="btn1",
    text="Click",
    data_action="submit",  # Extra field
    aria_label="Submit form"  # Extra field
)
```

These are available in the template context:

```html
<button
    id="{{ id }}"
    data-action="{{ data_action }}"
    aria-label="{{ aria_label }}"
>
    {{ text }}
</button>
```

## The `id` Field

Every component requires an `id`:

```python
button = Button(id="submit", text="Submit")  # OK
button = Button(text="Submit")  # Error: id is required
```

!!! tip "Auto-generated IDs"
    When using `Renderer` with `auto_id=True`, IDs are generated automatically for template-side rendering.
