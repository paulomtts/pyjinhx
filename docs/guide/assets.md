# Asset Collection

PyJinHx automatically handles JavaScript and CSS file collection for components.

## Automatic Asset Discovery

Place asset files next to your component with a matching kebab-case name:

```
components/ui/
├── my_widget.py      # MyWidget class
├── my_widget.html    # Template
├── my-widget.js      # Auto-collected JavaScript
└── my-widget.css     # Auto-collected CSS
```

Assets are automatically injected when the component renders — CSS as `<style>` tags before the HTML, JavaScript as `<script>` tags after.

### Naming Convention

| Class Name | JS File | CSS File |
|------------|---------|----------|
| `Button` | `button.js` | `button.css` |
| `ActionButton` | `action-button.js` | `action-button.css` |
| `MyWidget` | `my-widget.js` | `my-widget.css` |

### Deduplication

Assets are collected once per render session. If the same component type is rendered multiple times, each asset is only included once.

### Injection Order

Rendered output follows this structure:

```html
<style>/* component CSS */</style>
<div id="root-component">...</div>
<script>/* component JS */</script>
```

- **CSS** is injected **before** the HTML (styles apply immediately)
- **JS** is injected **after** the HTML (DOM elements exist when scripts run)
- Each component gets its own `<script>` and `<style>` tag (a syntax error in one script doesn't break others)
- Nested component assets are aggregated and injected at the root level

## Extra Asset Files

Add additional files using the `js` and `css` fields:

```python
widget = MyWidget(
    id="w1",
    title="Hello",
    js=["path/to/helper.js"],
    css=["path/to/theme.css"],
)
```

!!! warning
    Missing files emit a warning via the `pyjinhx` logger. Check your logs if assets aren't appearing.

## Disabling Inline Assets

To serve assets statically instead of inlining them:

```python
from pyjinhx import Renderer

Renderer.set_default_inline_js(False)
Renderer.set_default_inline_css(False)
```

When disabled:

- No `<script>` or `<style>` tags are injected
- The `js` and `css` fields are ignored
- Use `Finder.collect_javascript_files()` and `Finder.collect_css_files()` to discover files for static serving

## Static File Serving

Use `Finder` to get lists of asset files for static serving:

```python
from pyjinhx import Finder

finder = Finder(root="./components")

js_files = finder.collect_javascript_files(relative_to_root=True)
# ['ui/button.js', 'ui/dropdown.js', ...]

css_files = finder.collect_css_files(relative_to_root=True)
# ['ui/button.css', 'ui/dropdown.css', ...]
```

### Example: FastAPI Static Files

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pyjinhx import Finder

app = FastAPI()
app.mount("/static/components", StaticFiles(directory="components"), name="components")

finder = Finder(root="./components")
js_files = finder.collect_javascript_files(relative_to_root=True)
css_files = finder.collect_css_files(relative_to_root=True)

@app.get("/")
def index():
    styles = "\n".join(
        f'<link rel="stylesheet" href="/static/components/{css}">'
        for css in css_files
    )
    scripts = "\n".join(
        f'<script src="/static/components/{js}"></script>'
        for js in js_files
    )
    return f"""
    <html>
        <head>{styles}</head>
        <body>...{scripts}</body>
    </html>
    """
```
