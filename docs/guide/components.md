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


!!! tip "Auto-generated IDs (Template-side only)"
    When using `Renderer.get_default_renderer(auto_id=True)`, IDs are generated automatically for **template-side rendering only**.

    ```python
    # Template-side: auto_id works
    html = Renderer.get_default_renderer(auto_id=True).render('<Button text="OK"/>')
    # ID auto-generated as "button-{uuid}"

    # Python-side: auto_id doesn't apply
    button = Button(text="OK")  # ❌ Error: id is required
    ```

    For Python-side rendering, use the `default_factory` pattern shown above to auto-generate IDs.


## Template Discovery

Templates are automatically discovered based on the class name:

| Class Name | Template File | Priority |
|------------|---------------|----------|
| `Button` | `button.html` | 1st |
| `Button` | `button.jinja` | 2nd |
| `ActionButton` | `action_button.html` | 1st |
| `ActionButton` | `action_button.jinja` | 2nd |
| `UserCard` | `user_card.html` | 1st |
| `UserCard` | `user_card.jinja` | 2nd |

Template extensions are tried in order: `.html` first, then `.jinja`.

!!! warning "Template Location"
    **Python-side rendering** (`component.render()`): Templates must be in the **same directory** as the Python class file.

    **Template-side rendering** (`Renderer.render()`): Templates are found under the **Jinja loader root** directory (configured via `Renderer.set_default_environment()`).

## Extra Fields

Normally, if you pass extra fields to a class that inherits from Pydantic's `BaseModel`, it will raise an error:

```python
from pydantic import BaseModel
class Example(BaseModel):
    foo: int

Example(foo=1, bar=2)  # Raises ValidationError: extra fields not permitted
```

With `BaseComponent`, **extra fields are allowed and available in templates**. This allows you to pass dictionaries or data objects with additional fields beyond those defined in the class. Extra fields are stored by Pydantic and made available in the template context.

```python
from pyjinhx import BaseComponent

class Example(BaseComponent):
    id: str
    foo: int

ex = Example(id="test", foo=1, bar=2)  # No error!
# In template: {{ foo }} and {{ bar }} are both available
```

This is particularly useful when passing data from dynamic sources like databases or APIs where the structure may vary.