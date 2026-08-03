# Assets API

Public helpers for asset delivery, manifests, and cache-busted URLs.

See [Asset Collection](../guide/assets.md) for conceptual documentation and [Renderer](renderer.md) for `AssetMode` and `RenderSession`.

## AssetMode

```python
class AssetMode(str, Enum):
    INLINE = "inline"
    NONE = "none"
    LINK = "link"
```

How a kind of asset (CSS or JS) reaches the page for one render. `INLINE` writes the file's contents directly into the response, `LINK` emits a `<link>`/`<script src>` tag, `NONE` emits nothing.

## AssetManifest

```python
@dataclass(frozen=True)
class AssetManifest:
    stylesheets: tuple[str, ...]
    scripts: tuple[str, ...]
```

The resolved asset URLs for one render, split by kind, in path order.

## emit_assets

```python
def emit_assets(
    session: RenderSession, *, resolver: Callable[[Path], str] | None = None
) -> str
```

Return the markup for a session's accumulated assets, per its `css_mode`/`js_mode` delivery mode. `resolver` maps an asset path to the URL it is served from, and is required only when a kind is in `LINK` mode.

**Raises:** `OSError` if an asset file is missing or unreadable under `INLINE` mode; `ValueError` if a kind is in `LINK` mode and no resolver was given.

## asset_manifest

```python
def asset_manifest(
    session: RenderSession, *, resolver: Callable[[Path], str]
) -> AssetManifest
```

Return the resolved URLs of a session's accumulated assets as an `AssetManifest`, independent of `css_mode`/`js_mode`.

```python
from pyjinhx.assets import asset_manifest, resolver_with_hash

resolver = resolver_with_hash("/static/components", root="./components")
manifest = asset_manifest(session, resolver=resolver)
```

## hashed_filename

```python
def hashed_filename(path: Path, *, hash_len: int = 8) -> str
```

Return a cache-busted filename such as `button.a1b2c3d4.js`: the file's stem, a truncated SHA-256 digest of its contents, and its suffix, dot-joined.

**Raises:** `OSError` if the file is missing or unreadable.

## asset_token

```python
def asset_token(path: Path) -> str
```

Return the opaque dedup token the client reports for this asset, derived from the normalized path. Used for the `data-pjx-asset` attribute and the `X-PJX-Assets` header so the server can tell an asset the browser already has from one it does not.

## resolver_with_hash

```python
def resolver_with_hash(base_url: str, root: str) -> Callable[[Path], str]
```

Build an asset resolver that embeds a content hash in each filename, in the shape `asset_manifest()` expects.

- `base_url`: URL prefix the asset tree is served from; a trailing slash is ignored.
- `root`: Directory the asset paths are laid out under; the part of a path below it is preserved in the URL.

```python
from pyjinhx.assets import resolver_with_hash

resolver = resolver_with_hash("/static/components", root="./components")
```

## all_assets

```python
def all_assets() -> tuple[tuple[Path, ...], tuple[Path, ...]]
```

Every CSS and JS path declared by any component class, registry-wide rather than session-scoped. See [Discovery & Assets](finder.md#all_assets).
