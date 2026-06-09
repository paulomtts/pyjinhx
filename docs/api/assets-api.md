# Assets API

Public helpers for asset URL resolution, manifests, and layout preloading.

See [Asset Collection](../guide/assets.md) for conceptual documentation and [Renderer](renderer.md) for `AssetMode` and `RenderSession`.

## AssetManifest

```python
@dataclass(frozen=True)
class AssetManifest:
    stylesheets: tuple[str, ...]
    scripts: tuple[str, ...]
```

Resolved public URLs for assets collected during a render session. Built by `asset_manifest()` or `RenderSession.manifest()`.

## DEFAULT_RUNTIME_URL

```python
DEFAULT_RUNTIME_URL = "/static/pyjinhx/pjx.js"
```

Default public URL for the pyjinhx client runtime in `AssetMode.REFERENCE`. Override process-wide with `Renderer.set_default_runtime_url()`.

## runtime_asset_path

```python
def runtime_asset_path() -> str
```

Return the absolute filesystem path to the bundled `pjx.js` client runtime. Mount this directory as static files in production.

```python
from fastapi.staticfiles import StaticFiles
from pyjinhx.assets import runtime_asset_path
import os

app.mount(
    "/static/pyjinhx",
    StaticFiles(directory=os.path.dirname(runtime_asset_path())),
    name="pyjinhx",
)
```

## default_asset_url

```python
def default_asset_url(path: str, *, root: str) -> str
```

Map an absolute asset path to a default public URL under `/static/components/`. The runtime path maps to `DEFAULT_RUNTIME_URL`.

## make_default_asset_url_resolver

```python
def make_default_asset_url_resolver(root: str) -> AssetUrlResolver
```

Build a callable resolver using `default_asset_url()`. Pass to `Renderer.set_asset_url_resolver()` or `asset_manifest()`.

```python
from pyjinhx import Renderer
from pyjinhx.assets import make_default_asset_url_resolver

Renderer.set_asset_url_resolver(make_default_asset_url_resolver("./components"))
```

## hashed_filename

```python
def hashed_filename(path: str, *, hash_len: int = 8) -> str
```

Return a content-hash filename such as `button.a1b2c3d4.js`. Reads the file to compute a SHA-256 digest.

## resolver_with_hash

```python
def resolver_with_hash(base_url: str, root: str) -> AssetUrlResolver
```

Build an asset URL resolver that embeds a content hash in each filename. The runtime file is placed under `{base_url}/pyjinhx/{hashed}`.

```python
from pyjinhx import Renderer
from pyjinhx.assets import resolver_with_hash

Renderer.set_asset_url_resolver(resolver_with_hash("/static/components", root="./components"))
```

## asset_manifest

```python
def asset_manifest(session: RenderSession, *, resolver: AssetUrlResolver) -> AssetManifest
```

Build an `AssetManifest` from a `RenderSession` and a URL resolver. Equivalent to `session.manifest(resolver=resolver)`.

## Finder.layout_asset_tags

```python
def layout_asset_tags(self, *, resolver: AssetUrlResolver) -> Markup
```

Instance method on [`Finder`](finder.md). Emit `<link>` and `<script src>` tags for every component asset discovered under the finder's root. Use in layout shells to preload all component assets instead of per-page discovery.

```python
from pyjinhx.assets import make_default_asset_url_resolver
from pyjinhx.finder import Finder

finder = Finder(root="./components")
resolver = make_default_asset_url_resolver("./components")
head_tags = finder.layout_asset_tags(resolver=resolver)
```
