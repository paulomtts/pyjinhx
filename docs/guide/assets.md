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
<div id="root-component">...</div>
<script>/* component JS — INLINE mode */</script>
```

- **CSS** is injected **before** the HTML (styles apply immediately)
- **JS** is injected **after** the HTML (DOM elements exist when scripts run)
- Nested component assets are aggregated and injected at the root level

## Asset Delivery Modes

Configure how assets are delivered with `AssetMode`:

| Mode | CSS | JS | Use case |
|------|-----|----|----------|
| `INLINE` (default) | `<style>` | inline `<script>` | Zero-config demos |
| `NONE` | silence | silence | Production: serve a pre-built bundle |

```python
from pyjinhx import AssetMode, Renderer

Renderer.set_default_js_mode(AssetMode.NONE)
Renderer.set_default_css_mode(AssetMode.NONE)
```

When `NONE` mode is active no asset tags are emitted by the renderer. Link your pre-built CSS and JS bundles in the layout `<head>` manually — see [One-bundle deployment](#one-bundle-deployment) below.

### Reactive partial suppression

Full-page renders emit assets once at the layout root. Reactive partial responses and OOB swaps **never** re-ship assets — matching production expectations where the layout shell loads static files once.

### Client runtime (`pjx.js`)

Root full-page renders auto-inject the pyjinhx client runtime (`pjx.js`) as an inline `<script>` unless the request already carries `X-PJX-Mounted`.

For raw Jinja shells, call `client_script()` (`from pyjinhx.client import client_script`) and pass the result into the template context (e.g. `{"pjx_runtime": client_script()}`), then render with `{{ pjx_runtime }}` in `<head>` or `<body>`.

### CSP

For strict `script-src` policies, use `AssetMode.NONE`, serve assets from a pre-built bundle, and add a nonce or hash for the single inline runtime script (or serve `pjx.js` as a static file and link it yourself).

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
from pyjinhx.assets import asset_manifest, make_default_asset_url_resolver

resolver = make_default_asset_url_resolver("./components")
manifest = asset_manifest(session, resolver=resolver)
# manifest.stylesheets, manifest.scripts
```

## Layout Preload (All Components)

Ship every component asset from the layout shell instead of per-page discovery:

```python
from pyjinhx.assets import make_default_asset_url_resolver
from pyjinhx.finder import Finder

finder = Finder(root="./components")
resolver = make_default_asset_url_resolver("./components")
head_tags = finder.layout_asset_tags(resolver=resolver)
```

Combine with `AssetMode.NONE` and reactive partial suppression so HTMX swaps never re-ship assets.

## Cache-Busting

Embed content hashes in filenames:

```python
from pyjinhx.assets import hashed_filename, resolver_with_hash

hashed_filename("components/ui/button.js")  # button.a1b2c3d4.js
resolver = resolver_with_hash("/static/components", root="./components")
```

## Disabling Assets (`NONE` mode)

```python
from pyjinhx import AssetMode, Renderer

Renderer.set_default_js_mode(AssetMode.NONE)
Renderer.set_default_css_mode(AssetMode.NONE)
```

When disabled, no asset tags are emitted. Use `Finder.collect_javascript_files()` and `Finder.collect_css_files()` to discover files for fully manual static serving.

## Static File Serving

Use `Finder` to get lists of asset files for static serving:

```python
from pyjinhx.finder import Finder

finder = Finder(root="./components")

js_files = finder.collect_javascript_files(relative_to_root=True)
# ['ui/button.js', 'ui/dropdown.js', ...]

css_files = finder.collect_css_files(relative_to_root=True)
# ['ui/button.css', 'ui/dropdown.css', ...]
```

### Example: FastAPI with bundle serving

Build a bundle at startup (see [One-bundle deployment](#one-bundle-deployment)) and serve it as
a static file. Set both modes to `NONE` so components don't inline what the bundle already ships.

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pyjinhx import AssetMode, Renderer

app = FastAPI()
app.mount("/static/pyjinhx", StaticFiles(directory="path/to/pyjinhx/runtime"), name="pyjinhx")

Renderer.set_default_js_mode(AssetMode.NONE)
Renderer.set_default_css_mode(AssetMode.NONE)

@app.get("/")
def index():
    return str(MyApp(id="app").render())  # bundle already linked in layout <head>
```

## Asset helpers reference

| Symbol | Purpose |
|--------|---------|
| `DEFAULT_RUNTIME_URL` | Default `/static/pyjinhx/pjx.js` URL constant |
| `runtime_asset_path()` | Filesystem path to bundled `pjx.js` |
| `default_asset_url()` | Map absolute path → default public URL |
| `make_default_asset_url_resolver()` | Build a resolver from a component root |
| `hashed_filename()` | Content-hash a filename for cache-busting |
| `resolver_with_hash()` | Resolver that embeds hashes in URLs |
| `asset_manifest()` | Build `AssetManifest` from a `RenderSession` |
| `Finder.layout_asset_tags()` | Preload all component assets in a layout shell (instance method) |
| `Finder.all_assets()` | Every component asset as `(css_paths, js_paths)` — bundle input (instance method) |

See [Assets API](../api/assets-api.md) for signatures and examples.

## One-bundle deployment

For apps that prefer a single stylesheet/script over per-component references, enumerate every
component asset and serve two concatenated bundles with a content-hash ETag:

```python
import hashlib
import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from pyjinhx.finder import Finder

app = FastAPI()


def _build(paths: list[str], marker: str) -> tuple[bytes, str]:
    parts = []
    for path in paths:
        parts.append(marker.format(path=path).encode())
        parts.append(Path(path).read_bytes() + b"\n")
    payload = b"".join(parts)
    return payload, '"' + hashlib.md5(payload).hexdigest() + '"'


CSS_PATHS, JS_PATHS = Finder("app/components").all_assets()
CSS_BUNDLE, CSS_ETAG = _build(CSS_PATHS, "/* === {path} === */\n")
JS_BUNDLE, JS_ETAG = _build(JS_PATHS, "// === {path} ===\n")


def _bundle(request: Request, body: bytes, etag: str, media_type: str) -> Response:
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(body, media_type=media_type,
                    headers={"ETag": etag, "Cache-Control": "public, max-age=300"})


@app.get("/assets/bundle.css", include_in_schema=False)
def bundle_css(request: Request) -> Response:
    return _bundle(request, CSS_BUNDLE, CSS_ETAG, "text/css")


@app.get("/assets/bundle.js", include_in_schema=False)
def bundle_js(request: Request) -> Response:
    return _bundle(request, JS_BUNDLE, JS_ETAG, "application/javascript")
```

Reference the bundles from your layout `<head>` and render with
`Renderer.set_default_js_mode(AssetMode.NONE)` / `set_default_css_mode(AssetMode.NONE)` so
components stop inlining what the bundle already ships. Concatenation order is alphabetical;
if your app's cascade needs a specific sheet first, prepend it to the list before building.
To include the pyjinhx builtins, add `import pyjinhx.builtins` and build a second `Finder`:

```python
CSS_B, JS_B = Finder(os.path.join(os.path.dirname(pyjinhx.builtins.__file__), "ui")).all_assets()
```

Concatenate both lists before building the bundles.
