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

Assets are automatically injected when the component renders. The default mode inlines them as `<style>` and `<script>` tags.

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
<style>/* component CSS — INLINE mode */</style>
<link rel="stylesheet" href="...">  <!-- REFERENCE mode -->
<div id="root-component">...</div>
<script>/* component JS — INLINE mode */</script>
<script src="..."></script>           <!-- REFERENCE mode -->
```

- **CSS** is injected **before** the HTML (styles apply immediately)
- **JS** is injected **after** the HTML (DOM elements exist when scripts run)
- Nested component assets are aggregated and injected at the root level

## Asset Delivery Modes

Configure how assets are delivered with `AssetMode`:

| Mode | CSS | JS | Use case |
|------|-----|----|----------|
| `INLINE` (default) | `<style>` | inline `<script>` | Zero-config demos |
| `REFERENCE` | `<link href>` | `<script src>` | Production monoliths with static file serving |
| `NONE` | silence | silence | Manual static wiring (legacy `inline=False`) |

```python
from pyjinhx import AssetMode, Renderer

Renderer.set_default_js_mode(AssetMode.REFERENCE)
Renderer.set_default_css_mode(AssetMode.REFERENCE)
Renderer.set_asset_url_resolver(lambda path: f"/static/{path}")
```

When `REFERENCE` mode is active, co-located assets and `js`/`css` fields are collected into a per-render manifest and emitted as URL tags. Override the default URL builder with `Renderer.set_asset_url_resolver()`.

### Reactive partial suppression

Full-page renders emit assets once at the layout root. Reactive partial responses (`render(..., mounted=...)`) and OOB swaps **never** re-ship assets — matching production expectations where the layout shell loads static files once.

### Client asset dedup (REFERENCE mode, opt-in)

On HTMX requests, `pjx.js` reports asset URLs already in the DOM via the `X-PJX-Assets` header. When dedup is enabled, root renders emit only missing `<link>` / `<script src>` tags — useful for hx-boost full-page swaps.

```python
Renderer.set_default_asset_dedup(True)

@app.get("/page-b")
def page_b(request: Request):
    return str(PageB(id="app").render(client=request))
```

Partial renders ignore the asset header (no assets emitted). Dedup defaults to **off** for backward compatibility.

### Client runtime (`pjx.js`)

In `REFERENCE` mode, layout components (`base_layout=True`) emit `<script src="/static/pyjinhx/pjx.js">` instead of inlining the runtime. Mount the packaged file from `pyjinhx/runtime/pjx.js` or override with `Renderer.set_default_runtime_url()`.

For raw Jinja shells, use `client_script(mode=AssetMode.REFERENCE)`.

### CSP

`REFERENCE` mode avoids inline scripts entirely — compatible with strict `script-src` policies without nonce plumbing.

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

## Per-Render Manifest

Inspect which assets a render used:

```python
from pyjinhx import asset_manifest, make_default_asset_url_resolver

resolver = make_default_asset_url_resolver("./components")
manifest = asset_manifest(session, resolver=resolver)
# manifest.stylesheets, manifest.scripts
```

## Layout Preload (All Components)

Ship every component asset from the layout shell instead of per-page discovery:

```python
from pyjinhx import Finder, layout_asset_tags, make_default_asset_url_resolver

finder = Finder(root="./components")
resolver = make_default_asset_url_resolver("./components")
head_tags = layout_asset_tags(finder, resolver=resolver)
```

Combine with `AssetMode.REFERENCE` and reactive partial suppression so HTMX swaps never re-ship assets.

## Cache-Busting

Embed content hashes in filenames:

```python
from pyjinhx import hashed_filename, resolver_with_hash

hashed_filename("components/ui/button.js")  # button.a1b2c3d4.js
resolver = resolver_with_hash("/static/components", root="./components")
```

## Disabling Assets (`NONE` mode)

```python
from pyjinhx import AssetMode, Renderer

Renderer.set_default_js_mode(AssetMode.NONE)
Renderer.set_default_css_mode(AssetMode.NONE)
```

Legacy bool shims still work: `Renderer.set_default_inline_js(False)`.

When disabled, no asset tags are emitted. Use `Finder.collect_javascript_files()` and `Finder.collect_css_files()` to discover files for fully manual static serving.

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

### Example: FastAPI with REFERENCE mode

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pyjinhx import AssetMode, Finder, Renderer, make_default_asset_url_resolver

app = FastAPI()
app.mount("/static/components", StaticFiles(directory="components"), name="components")
app.mount(
    "/static/pyjinhx",
    StaticFiles(directory="path/to/pyjinhx/runtime"),
    name="pyjinhx",
)

Renderer.set_default_js_mode(AssetMode.REFERENCE)
Renderer.set_default_css_mode(AssetMode.REFERENCE)
Renderer.set_asset_url_resolver(make_default_asset_url_resolver("components"))

@app.get("/")
def index():
    return str(MyApp(id="app").render())  # emits link/script refs for used components
```

### Example: Django

```python
from django.templatetags.static import static
from pyjinhx import Renderer

Renderer.set_asset_url_resolver(lambda path: static(path_relative_to_static_root(path)))
```

Map each absolute asset path to your `{% static %}` URL in the resolver callback.
