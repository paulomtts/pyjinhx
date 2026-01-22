# HTMX

PyJinHx components work seamlessly with [HTMX](https://htmx.org/) for building interactive web applications with minimal JavaScript.

## Setup

Install PyJinHx:

```bash
pip install pyjinhx
```

Include HTMX in your HTML:

```html
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
```

## Project Structure

```
my_app/
├── components/
│   └── ui/
│       ├── button.py
│       ├── button.html
│       ├── counter.py
│       ├── counter.html
│       └── counter.js
└── index.html
```

## Basic Example

### Component Class

```python
# components/ui/button.py
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    endpoint: str = "/clicked"
```

### Component Template with HTMX

```html
<!-- components/ui/button.html -->
<button
    id="{{ id }}"
    hx-post="{{ endpoint }}"
    hx-vals='{"button_id": "{{ id }}"}'
    hx-target="#result"
    hx-swap="innerHTML"
>
    {{ text }}
</button>
```

### HTML Page

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body>
    <Button id="click-me" text="Click Me" endpoint="/clicked"></Button>
    <div id="result"></div>
</body>
</html>
```

Use PyJinHx's `Renderer` to process the HTML:

```python
from pyjinhx import Renderer

Renderer.set_default_environment("./components")

with open("index.html", "r") as f:
    source = f.read()

html = Renderer.get_default_renderer().render(source)
```

## Counter Example

A complete example showing state management with HTMX.

### Counter Component

```python
# components/ui/counter.py
from pyjinhx import BaseComponent


class Counter(BaseComponent):
    id: str
    value: int = 0
```

```html
<!-- components/ui/counter.html -->
<div id="{{ id }}" class="counter">
    <button
        hx-post="/counter/decrement"
        hx-vals='{"counter_id": "{{ id }}", "value": "{{ value }}"}'
        hx-target="#{{ id }}"
        hx-swap="outerHTML"
    >
        -
    </button>

    <span class="value">{{ value }}</span>

    <button
        hx-post="/counter/increment"
        hx-vals='{"counter_id": "{{ id }}", "value": "{{ value }}"}'
        hx-target="#{{ id }}"
        hx-swap="outerHTML"
    >
        +
    </button>
</div>
```

### Component JavaScript

```javascript
// components/ui/counter.js
document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.classList.contains('counter')) {
        console.log('Counter was updated!');
        // Add any additional client-side logic here
    }
});
```

## HTMX Patterns with PyJinHx

### Use `hx-swap="outerHTML"` for Component Updates

When returning a full component, use `outerHTML` to replace the entire element:

```html
<!-- components/ui/item.html -->
<div id="{{ id }}" class="item">
    <h3>{{ title }}</h3>
    <button
        hx-post="/items/{{ id }}/update"
        hx-target="#{{ id }}"
        hx-swap="outerHTML"
    >
        Update
    </button>
</div>
```

### Pass Component ID in Requests

Include the component ID so you can target the right element:

```html
<!-- components/ui/form.html -->
<form
    id="{{ id }}"
    hx-post="/submit"
    hx-vals='{"form_id": "{{ id }}"}'
    hx-target="#{{ id }}"
    hx-swap="outerHTML"
>
    <!-- form fields -->
</form>
```

### Conditional HTMX Attributes

Use Jinja conditionals to control HTMX behavior:

```html
<!-- components/ui/button.html -->
<button
    id="{{ id }}"
    {% if endpoint %}
    hx-post="{{ endpoint }}"
    hx-target="#result"
    hx-swap="innerHTML"
    {% endif %}
>
    {{ text }}
</button>
```

### Loading States

Show loading indicators during HTMX requests:

```html
<!-- components/ui/button.html -->
<button
    id="{{ id }}"
    hx-post="{{ endpoint }}"
    hx-indicator="#spinner"
>
    <span class="button-text">{{ text }}</span>
    <span id="spinner" class="htmx-indicator">Loading...</span>
</button>
```

## Tips

### Component JavaScript with HTMX Events

If your component has JavaScript that needs to run after HTMX swaps, use HTMX events:

```javascript
// components/ui/widget.js
document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.classList.contains('widget')) {
        // Initialize widget after swap
        initializeWidget(event.detail.target);
    }
});
```

### Server-Sent Events

HTMX supports Server-Sent Events (SSE) for real-time updates:

```html
<!-- components/ui/feed.html -->
<div
    id="{{ id }}"
    hx-sse="connect:/events"
    hx-swap="beforeend"
>
    <!-- Feed items will be appended here -->
</div>
```

### WebSockets

HTMX also supports WebSockets:

```html
<!-- components/ui/chat.html -->
<div
    id="{{ id }}"
    hx-ws="connect:/ws"
    hx-swap="beforeend"
>
    <!-- Messages will be appended here -->
</div>
```
