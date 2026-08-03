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
| `LINK` | `<link rel="stylesheet">` | `<script src>` | Serve assets as static files, still per-render |
| `NONE` | silence | silence | Production: serve a pre-built bundle |

`LINK` mode requires a `resolver` (a `Callable[[Path], str]` mapping an asset path to the URL
it's served from) — pass one to `emit_assets()`/`asset_manifest()`, or it raises `ValueError`.
`resolver_with_hash` (see [Cache-Busting](#cache-busting)) is a ready-made resolver.

```python
from pyjinhx import AssetMode
from pyjinhx.session import RenderSession

session = RenderSession(template_dir="./components")
session.css_mode = AssetMode.NONE
session.js_mode = AssetMode.NONE
```

`css_mode`/`js_mode` are per-`RenderSession` attributes (each defaults to `AssetMode.INLINE`)
rather than a process-wide switch — set them on the session you pass to `render()`. When
`NONE` mode is active no asset tags are emitted for that render. Link your pre-built CSS and
JS bundles in the layout `<head>` manually — see [One-bundle deployment](#one-bundle-deployment)
below.

### Reactive partial suppression

Full-page renders emit assets once at the layout root. Reactive partial responses and OOB swaps **never** re-ship assets — matching production expectations where the layout shell loads static files once.

### Client runtime (`pjx.js`)

Root full-page renders auto-inject the pyjinhx client runtime (`pjx.js`, vendored alongside a
pinned copy of htmx) as an inline `<script>` unless the request already carries
`X-PJX-Mounted`. This is handled by `inject_runtime(session, request)` from
`pyjinhx.client.inject`, which records the script on the session for `emit_assets` to include.

For a raw Jinja shell that renders outside pyjinhx's own pipeline, read the runtime source
directly and embed it yourself:

```python
from pyjinhx.client import read_pjx_runtime, read_vendored_htmx

pjx_runtime = f"<script>{read_vendored_htmx()}{read_pjx_runtime()}</script>"
# pass pjx_runtime into your template context and render it in <head> or <body>
```

### CSP

For strict `script-src` policies, use `AssetMode.NONE`, serve assets from a pre-built bundle, and add a nonce or hash for the single inline runtime script (or serve `pjx.js` as a static file and link it yourself).

## Per-Render Manifest

Inspect which assets a render used. `asset_manifest` takes any resolver shaped
`Callable[[Path], str]` — `resolver_with_hash` builds one that also cache-busts filenames:

```python
from pyjinhx.assets import asset_manifest, resolver_with_hash

resolver = resolver_with_hash("/static/components", root="./components")
manifest = asset_manifest(session, resolver=resolver)
# manifest.stylesheets, manifest.scripts
```

## Layout Preload (All Components)

Ship every component asset from the layout shell instead of per-page discovery. `all_assets()`
walks every registered component class (not just the ones a given render used) and returns its
CSS and JS paths, deduped and sorted:

```python
from pyjinhx.assets import all_assets, resolver_with_hash

resolver = resolver_with_hash("/static/components", root="./components")
css_paths, js_paths = all_assets()
head_tags = [f'<link rel="stylesheet" href="{resolver(p)}">' for p in css_paths]
head_tags += [f'<script src="{resolver(p)}"></script>' for p in js_paths]
```

Combine with `AssetMode.NONE` and reactive partial suppression so HTMX swaps never re-ship assets.

!!! note "Import components before calling `all_assets()`"
    `all_assets()` only sees classes Python has already imported (it walks `BaseComponent`'s
    subclass tree), so import your component package — or call `setup(components_root=...)` —
    before calling it from a build script.

## Cache-Busting

Embed content hashes in filenames:

```python
from pathlib import Path
from pyjinhx.assets import hashed_filename, resolver_with_hash

hashed_filename(Path("components/ui/button.js"))  # "button.a1b2c3d4.js"
resolver = resolver_with_hash("/static/components", root="./components")
```

## Disabling Assets (`NONE` mode)

```python
from pyjinhx import AssetMode
from pyjinhx.session import RenderSession

session = RenderSession(template_dir="./components")
session.css_mode = AssetMode.NONE
session.js_mode = AssetMode.NONE
```

When disabled, no asset tags are emitted. Use `all_assets()` (below) to discover files for
fully manual static serving.

## Static File Serving

Use `all_assets()` to get every component's asset paths for static serving:

```python
from pyjinhx.assets import all_assets

css_paths, js_paths = all_assets()
# each is a sorted tuple[Path, ...], e.g. (Path("ui/button.css"), Path("ui/dropdown.css"), ...)
```

### Example: FastAPI with bundle serving

Build a bundle at startup (see [One-bundle deployment](#one-bundle-deployment)) and serve it as
a static file. Set both modes to `NONE` so components don't inline what the bundle already ships.

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pyjinhx import AssetMode
from pyjinhx.session import RenderSession

app = FastAPI()
app.mount(
    "/static/pyjinhx", StaticFiles(directory="path/to/pyjinhx/runtime"), name="pyjinhx"
)


@app.get("/")
def index():
    session = RenderSession(template_dir="./components")
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE
    return str(
        MyApp(id="app").render(session)
    )  # bundle already linked in layout <head>
```

## Asset helpers reference

| Symbol | Purpose |
|--------|---------|
| `emit_assets()` | Markup for a session's accumulated assets, per delivery mode |
| `asset_manifest()` | Build an `AssetManifest` (resolved URLs) from a `RenderSession` |
| `all_assets()` | Every registered component's CSS/JS paths as `(css_paths, js_paths)` |
| `hashed_filename()` | Content-hash a `Path` for cache-busting (`hash_len=8` by default) |
| `asset_token()` | Opaque dedup token for an asset path (used by `X-PJX-Assets`) |
| `resolver_with_hash()` | Build a resolver that embeds a content hash in each URL |

See [Assets API](../api/assets-api.md) for signatures and examples.

## One-bundle deployment

For apps that prefer a single stylesheet/script over per-component references, enumerate every
component asset and serve two concatenated bundles with a content-hash ETag:

```python
import hashlib
from pathlib import Path

from fastapi import FastAPI, Request, Response
from pyjinhx.assets import all_assets

app = FastAPI()


def _build(paths: tuple[Path, ...], marker: str) -> tuple[bytes, str]:
    parts = []
    for path in paths:
        parts.append(marker.format(path=path).encode())
        parts.append(path.read_bytes() + b"\n")
    payload = b"".join(parts)
    return payload, '"' + hashlib.md5(payload).hexdigest() + '"'


CSS_PATHS, JS_PATHS = all_assets()
CSS_BUNDLE, CSS_ETAG = _build(CSS_PATHS, "/* === {path} === */\n")
JS_BUNDLE, JS_ETAG = _build(JS_PATHS, "// === {path} ===\n")


def _bundle(request: Request, body: bytes, etag: str, media_type: str) -> Response:
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        body,
        media_type=media_type,
        headers={"ETag": etag, "Cache-Control": "public, max-age=300"},
    )


@app.get("/assets/bundle.css", include_in_schema=False)
def bundle_css(request: Request) -> Response:
    return _bundle(request, CSS_BUNDLE, CSS_ETAG, "text/css")


@app.get("/assets/bundle.js", include_in_schema=False)
def bundle_js(request: Request) -> Response:
    return _bundle(request, JS_BUNDLE, JS_ETAG, "application/javascript")
```

Reference the bundles from your layout `<head>` and set `session.js_mode = AssetMode.NONE` /
`session.css_mode = AssetMode.NONE` on the `RenderSession` you render with, so components stop
inlining what the bundle already ships. Concatenation order is alphabetical; if your app's
cascade needs a specific sheet first, prepend it to the list before building.
`all_assets()` already walks every registered `BaseComponent` subclass — including the pyjinhx
builtins — as long as they've been imported, so `import pyjinhx.builtins` before calling it is
enough to fold builtin assets into the same bundle; no separate call is needed.
