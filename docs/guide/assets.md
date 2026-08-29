# Asset Collection

PyJinHx automatically handles JavaScript and CSS file collection for components.

## Automatic Asset Discovery

Place asset files next to your component, under the same snake_case stem as its template:

```
components/ui/
├── my_widget.py      # MyWidget class
├── my_widget.pjx     # Template
├── my_widget.js      # Auto-collected JavaScript
└── my_widget.css     # Auto-collected CSS
```

Assets are automatically injected when the component renders. The default mode inlines them as `<style>` and `<script>` tags.

### Naming Convention

| Class Name | JS File | CSS File |
|------------|---------|----------|
| `Button` | `button.js` | `button.css` |
| `ActionButton` | `action_button.js` | `action_button.css` |
| `MyWidget` | `my_widget.js` | `my_widget.css` |

The probe walks the inheritance chain the same way template resolution does, so `class DangerButton(PJXButton)` with no files of its own inherits `pjx_button.css`.

### Deduplication

Assets are collected once per render session. If the same component type is rendered multiple times, each asset is only included once.

### Injection Order

Rendered output follows this structure:

```html
<style data-pjx-asset="...">/* component CSS — INLINE mode */</style>
<div id="root-component">...</div>
<script>/* component JS — INLINE mode */</script>
```

- **CSS** is injected **before** the HTML (styles apply immediately), stamped with a
  `data-pjx-asset` token — the invariant is that every style pyjinhx puts on a page
  carries one, and every tokened style ends up in `<head>`. `pjx.js` promotes an
  inline `<style>` there on load and after every htmx settle, so a style that lands
  inside a region a later swap replaces survives instead of being deleted with it,
  and the token also tells the server the browser already has the file (see
  [Swap-in assets](#swap-in-assets-the-delta)).
- **JS** is injected **after** the HTML (DOM elements exist when scripts run), untokened —
  `pjx.js` never relocates a `<script>` node (re-appending one would re-execute it), so
  a token nobody reads would be dead weight.
- Nested component assets are aggregated and injected at the root level

### CSS Ordering Guarantee

A builtin's rule and the app rule restyling it (`class="pjx-popover__trigger
my-trigger"`, both a single class) tie at specificity, and a tied pair
resolves by document order. **Builtin CSS always emits before application
CSS** — in `emit_assets()`, in `missing_asset_oob()`'s post-paint fragments,
and in how `pjx.js` relocates a late-arriving builtin stylesheet into
`<head>` — so a bare app selector reliably wins that tie, in every delivery
mode and at any point in a session, regardless of which half happens to load
first.

This only settles *ties*. A builtin rule that is already more specific than
the app's own (an `--open`/`--active` state class, say) still wins on
specificity, exactly as before — nothing here changes how specificity itself
is compared. If you need to beat a more-specific builtin rule, qualify your
selector with the builtin's class (`.pjx-popover__trigger.my-trigger { }`),
same as always.

`all_assets()` (used for [one-bundle deployment](#one-bundle-deployment))
does not apply this ordering — it returns one alphabetically sorted tuple
across every registered component. Building your own bundle from it and
relying on this guarantee inside that bundle means sorting builtin paths
first yourself. See [ADR 0003](../decisions/0003-builtin-css-ordering.md) for
the full rationale.

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
from pyjinhx import AssetMode, RenderSession

session = RenderSession()
session.css_mode = AssetMode.NONE
session.js_mode = AssetMode.NONE
```

`css_mode`/`js_mode` are per-`RenderSession` attributes (each defaults to `AssetMode.INLINE`)
rather than a process-wide switch — set them on the session that render uses. In a wired app
that session is the one `PjxScopeMiddleware` opens per request; see
[Choosing a mode in a wired app](#choosing-a-mode-in-a-wired-app). When
`NONE` mode is active no asset tags are emitted for that render. Link your pre-built CSS and
JS bundles in the layout `<head>` manually — see [One-bundle deployment](#one-bundle-deployment)
below.

### Swap-in assets (the delta)

Full-page renders emit assets once at the layout root. An OOB swap carries markup only — but a region appearing for the first time in this page's life still needs its stylesheet and its script, so the response composer ships the **difference**: the client reports the tokens it already has in `X-PJX-Assets`, `missing_asset_oob()` diffs that against what the walk's candidates require, and the shortfall is appended as head-targeted OOB fragments (`hx-swap-oob="beforeend:head"`, stamped `data-pjx-asset`) that `pjx.js` relocates on arrival. Nothing the client already reports is sent twice.

!!! note "INLINE mode only, today"
    The delta is built from the session's `css_mode`/`js_mode`, and only `INLINE` is delivered: `compose()` has no URL resolver to hand down, so a `LINK`-mode app ships no swap-in assets and must preload them from the layout shell (see [Layout Preload](#layout-preload-all-components)). `NONE` mode suppresses them as intended.

A component returned directly as an htmx fragment response (rather than nested inside a
full page) goes through the same `emit_assets()`/`missing_asset_oob()` pair as a full-page
render — its stylesheet is still tokened, so a poll-and-replace fragment (`hx-trigger="every
..."`, `hx-swap="outerHTML"`) never grows an unbounded pile of orphaned `<style>` nodes: each
swap's inline style is promoted to `<head>` on the next settle and deduped against the one
already there.

### Client runtime (`pjx.js`)

Root full-page renders auto-inject the pyjinhx client runtime (`pjx.js`, vendored alongside a
pinned copy of htmx) as an inline `<script>` unless the request already carries
`X-PJX-Mounted`. `setup(app)` wires this for you — internally it is
`inject_runtime(session, request)`, which records the script on the session for
`emit_assets` to include. You never call it yourself.

For a raw Jinja shell that renders outside pyjinhx's own pipeline, assemble the tags
yourself — see [Reactivity](../reactivity.md#ship-the-client-runtime) for the full snippet
and why each piece is there. In short: the readers return bare source with no `<script>`
wrapper, `pjx.js` needs htmx loaded first, and the result must be handed to the template as
`Markup` or Jinja will autoescape it into visible page text.

### CSP

For strict `script-src` policies, use `AssetMode.NONE`, serve assets from a pre-built bundle, and add a nonce or hash for the single inline runtime script (or serve `pjx.js` as a static file and link it yourself).

## Per-Render Manifest

!!! warning "`pyjinhx.assets` is not yet public"
    Everything in the rest of this page — `asset_manifest()`, `all_assets()`,
    `resolver_with_hash()`, `hashed_filename()`, `emit_assets()`, `asset_token()` — lives
    in `pyjinhx.assets`, which is **not** in `pyjinhx.__all__`. These are the only spelling
    for build-time asset enumeration today, so they are documented here, but the module path
    may change. Only `AssetMode` and `RenderSession` are public.

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

Combine with `AssetMode.NONE` so neither the cold render nor an HTMX swap ships anything the preloaded bundle already covers.

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
from pyjinhx import AssetMode, RenderSession

session = RenderSession()
session.css_mode = AssetMode.NONE
session.js_mode = AssetMode.NONE
```

When disabled, no asset tags are emitted. Use `all_assets()` (below) to discover files for
fully manual static serving.

### Choosing a mode in a wired app

Under `setup(app)` you do not build the session — `PjxScopeMiddleware` does, once per
request — so set the modes from inside the scope. A FastAPI dependency runs there:

```python
from fastapi import Depends, FastAPI
from pyjinhx import AssetMode, setup
from pyjinhx.session import current_session  # not yet public


def bundled_assets():
    session = current_session()
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE


app = FastAPI(dependencies=[Depends(bundled_assets)])
setup(app, components_root="./components")
```

!!! note "Not yet public"
    `current_session()` lives in `pyjinhx.session`, which is not exported from `pyjinhx`.
    There is no public per-app asset-mode setting yet; when there is, it will replace this.

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
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from pyjinhx import AssetMode, setup
from pyjinhx.session import current_session  # not yet public

from components import MyApp


def bundled_assets():
    session = current_session()
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE


app = FastAPI(dependencies=[Depends(bundled_assets)])
app.mount(
    "/static/pyjinhx", StaticFiles(directory="path/to/pyjinhx/runtime"), name="pyjinhx"
)
setup(app, components_root="./components")


@app.get("/")
def index():
    return MyApp(id="app")  # bundle already linked in layout <head>
```

The handler returns the component; the adapter renders it, and with both modes `NONE` it
emits no `<style>`/`<script>` of its own.

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

Reference the bundles from your layout `<head>` and set both modes to `AssetMode.NONE` on the
request's session (see [Choosing a mode in a wired app](#choosing-a-mode-in-a-wired-app)), so
components stop inlining what the bundle already ships. Concatenation order is alphabetical; if your app's
cascade needs a specific sheet first, prepend it to the list before building.
`all_assets()` already walks every registered `BaseComponent` subclass — including the pyjinhx
builtins — as long as they've been imported, so `import pyjinhx.builtins` before calling it is
enough to fold builtin assets into the same bundle; no separate call is needed.
