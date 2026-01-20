# BaseComponent

The base class for all PyJinHx components.

## Overview

`BaseComponent` combines Pydantic's validation with Jinja2 templating to create reusable UI components.

```python
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"
```

## API Reference

::: pyjinhx.BaseComponent
    options:
      members:
        - render
        - __html__
      show_root_heading: true
      heading_level: 3

## NestedComponentWrapper

When components are nested, they're wrapped in `NestedComponentWrapper` to provide access to both rendered HTML and original props.

::: pyjinhx.base.NestedComponentWrapper
    options:
      show_root_heading: true
      heading_level: 3

## Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier for the component instance |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `js` | `list[str]` | `[]` | Paths to extra JavaScript files |

## Usage Examples

### Basic Component

```python
from pyjinhx import BaseComponent


class Alert(BaseComponent):
    id: str
    message: str
    level: str = "info"


alert = Alert(id="warning", message="Please confirm", level="warning")
html = alert.render()
```

### With Nested Components

```python
class Card(BaseComponent):
    id: str
    title: str
    action: Button


card = Card(
    id="hero",
    title="Welcome",
    action=Button(id="cta", text="Get Started")
)
```

### With Extra Assets

```python
widget = Widget(
    id="w1",
    title="Dashboard",
    js=["path/to/chart.js"],
)
```

### Extra Fields

Components accept extra fields:

```python
button = Button(
    id="submit",
    text="Submit",
    data_loading="true",  # Extra field
    aria_label="Submit form"  # Extra field
)
```

## Template Context

All component fields are available in the template:

```html
<button
    id="{{ id }}"
    class="btn btn-{{ variant }}"
    {% if data_loading %}data-loading="{{ data_loading }}"{% endif %}
>
    {{ text }}
</button>
```
