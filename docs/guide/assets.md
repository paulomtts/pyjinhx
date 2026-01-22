# JavaScript Collection

PyJinHx automatically handles JavaScript file collection.

## Automatic JavaScript Collection

Place a JavaScript file next to your component with a matching kebab-case name:

```
components/ui/
├── my_widget.py      # MyWidget class
├── my_widget.html    # Template
└── my-widget.js      # Auto-collected JavaScript
```

The JavaScript is automatically injected when the component renders:

```python
class MyWidget(BaseComponent):
    id: str
    title: str

widget = MyWidget(id="w1", title="Hello")
html = widget.render()
```

Output:

```html
<script>
// Contents of my-widget.js
</script>
<div id="w1">Hello</div>
```

### Naming Convention

| Class Name | JavaScript File |
|------------|-----------------|
| `Button` | `button.js` |
| `ActionButton` | `action-button.js` |
| `MyWidget` | `my-widget.js` |

### Deduplication

JavaScript is collected once per render session. If the same component type is rendered multiple times, the script is only included once.

### Script Injection Location

Scripts are injected at the beginning of the rendered output for root components:

```html
<script>
// All collected JavaScript
</script>
<div id="root-component">
    ...
</div>
```

Nested component scripts are aggregated and injected at the root level, not inline with each component.

### Disabling Inline JavaScript

To serve JavaScript files statically instead of inlining them, disable inline JS collection:

```python
from pyjinhx import Renderer

# Disable globally - affects all components including BaseComponent.render()
Renderer.set_default_inline_js(False)

# Now renders without <script> tags
widget = MyWidget(id="w1", title="Hello")
html = widget.render()  # No inline scripts
```

When `inline_js=False`:

- No `<script>` tags are injected into rendered output
- The component's `js` field is ignored
- Use `Finder.collect_javascript_files()` to discover JS files for static serving

See [Static File Serving](#static-file-serving) for how to serve JS files.

### Extra JavaScript Files

Add additional JavaScript files using the `js` field:

```python
widget = MyWidget(
    id="w1",
    title="Hello",
    js=[
        "path/to/helper.js",
        "path/to/another.js"
    ]
)
```

!!! note
    Missing files are silently ignored. This allows optional JavaScript dependencies.

### Example: Component with Assets

```
components/
└── ui/
    ├── dropdown.py
    ├── dropdown.html
    └── dropdown.js
```

```python
# dropdown.py
from pyjinhx import BaseComponent

class Dropdown(BaseComponent):
    id: str
    options: list[str]
    selected: str = ""
```

```html
<!-- dropdown.html -->
<select id="{{ id }}" class="dropdown">
    {% for option in options %}
        <option value="{{ option }}"
                {% if option == selected %}selected{% endif %}>
            {{ option }}
        </option>
    {% endfor %}
</select>
```

```javascript
// dropdown.js
document.querySelectorAll('.dropdown').forEach(el => {
    el.addEventListener('change', (e) => {
        console.log('Selected:', e.target.value);
    });
});
```

```python
dropdown = Dropdown(
    id="country",
    options=["USA", "Canada", "Mexico"],
    selected="Canada"
)
html = dropdown.render()
```

Output:

```html
<script>
document.querySelectorAll('.dropdown').forEach(el => {
    el.addEventListener('change', (e) => {
        console.log('Selected:', e.target.value);
    });
});
</script>
<select id="country" class="dropdown">
    <option value="USA">USA</option>
    <option value="Canada" selected>Canada</option>
    <option value="Mexico">Mexico</option>
</select>
```


## Static File Serving

For production deployments, you may want to serve JavaScript files statically rather than inlining them. Use `Finder.collect_javascript_files()` to get a list of all JavaScript files in your components directory:

```python
from pyjinhx import Finder

finder = Finder(root="./components")

# Get absolute paths
js_files = finder.collect_javascript_files()
# ['/app/components/ui/button.js', '/app/components/ui/dropdown.js', ...]

# Get relative paths (useful for URL generation)
js_files = finder.collect_javascript_files(relative_to_root=True)
# ['ui/button.js', 'ui/dropdown.js', ...]
```

### Example: FastAPI Static Files

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pyjinhx import Finder

app = FastAPI()

# Mount components directory for static JS serving
app.mount("/static/components", StaticFiles(directory="components"), name="components")

# Get list of JS files for inclusion in HTML
finder = Finder(root="./components")
js_files = finder.collect_javascript_files(relative_to_root=True)

@app.get("/")
def index():
    scripts = "\n".join(
        f'<script src="/static/components/{js}"></script>'
        for js in js_files
    )
    return f"""
    <html>
        <head>{scripts}</head>
        <body>...</body>
    </html>
    """
```