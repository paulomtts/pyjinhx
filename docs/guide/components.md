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

PyJinHX uses **Jinja2** templates for it's components:

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

Every component requires an `id`:

```python
button = Button(id="submit", text="Submit")  # OK
button = Button(text="Submit")  # Error: id is required
```

!!! tip "Customizing the `id` Field"
    You can override the `id` field in your component to automatically generate a value using Pydantic's `default_factory`. For example, to have a random UUID assigned if no `id` is passed:

    ```python
    import uuid
    from pyjinhx import BaseComponent
    from pydantic import Field

    class MyComponent(BaseComponent):
        id: str = Field(default_factory=lambda: str(uuid.uuid4()))
        # ... other fields ...
    ```

    This way, when you instantiate `MyComponent()` without providing an `id`, a unique value will be generated.


!!! tip "Auto-generated IDs"
    When using `Renderer` with `auto_id=True`, IDs are generated automatically for template-side rendering.


## Template Discovery

Templates are automatically discovered based on the class name:

| Class Name | Template File |
|------------|---------------|
| `Button` | `button.html` or `button.jinja` |
| `ActionButton` | `action_button.html` or `action_button.jinja` |
| `UserCard` | `user_card.html` or `user_card.jinja` |

!!! warning "Template Location Requirement"
    Templates must be in the same directory as the Python class file.

## Extra Fields

Normally, if you pass extra fields to a class that inherits from Pydantic's `BaseModel`, it will raise an error:

```python
from pydantic import BaseModel
class Example(BaseModel):
    foo: int

Example(foo=1, bar=2)  # Raises ValidationError: extra fields not permitted
```

With `BaseComponent`, **extra fields are simply ignored during rendering**. This allows you to pass dictionaries or data objects with additional fields—only those specified in the component's signature are used. This is particularly useful when passing data from dynamic sources.

```python
from pyjinhx import BaseComponent

class Example(BaseComponent):
    foo: int

ex = Example(foo=1, bar=2)  # No error! 'bar' is just ignored
```