# Renderer

Shared rendering engine used by `BaseComponent` rendering and HTML-like custom-tag rendering.

## Class

### Renderer

This renderer centralizes:
- Jinja template loading (by component class or explicit file/source)
- Expansion of PascalCase custom tags inside rendered markup
- JavaScript and CSS collection/deduping and root-level asset injection
- Rendering of HTML-like source strings into component output

#### Constructor

##### __init__()

```python
def __init__(
    environment: Environment,
    *,
    auto_id: bool = True,
    js_mode: AssetMode | None = None,
    css_mode: AssetMode | None = None,
) -> None
```

Initialize a Renderer with the given Jinja environment.

**Parameters:**
- `environment` (Environment): The Jinja2 Environment to use for template rendering
- `auto_id` (bool): If True (default), generate UUIDs for components without explicit IDs
- `js_mode` (AssetMode | None): JavaScript delivery mode. Defaults to the class-level setting
- `css_mode` (AssetMode | None): CSS delivery mode. Defaults to the class-level setting

#### Class Methods

##### get_default_renderer()

```python
@classmethod
def get_default_renderer(
    *,
    auto_id: bool = True,
    js_mode: AssetMode | None = None,
    css_mode: AssetMode | None = None,
) -> Renderer
```

Return a cached default renderer instance.

**Parameters:**
- `auto_id` (bool): If True, generate UUIDs for components without explicit IDs
- `js_mode` (AssetMode | None): JavaScript delivery mode
- `css_mode` (AssetMode | None): CSS delivery mode

**Returns:** A Renderer instance cached by environment identity, `auto_id`, asset modes, and resolver identity.

##### set_default_js_mode()

```python
@classmethod
def set_default_js_mode(mode: AssetMode) -> None
```

Set the process-wide default JavaScript asset delivery mode.

##### set_default_css_mode()

```python
@classmethod
def set_default_css_mode(mode: AssetMode) -> None
```

Set the process-wide default CSS asset delivery mode.

##### get_default_environment()

```python
@classmethod
def get_default_environment() -> Environment
```

Return the default Jinja environment, auto-initializing if needed.

If no environment is configured, one is created using auto-detected project root.

**Returns:** The default Jinja Environment instance.

##### set_default_environment()

```python
@classmethod
def set_default_environment(
    environment: Environment | str | os.PathLike[str] | None
) -> None
```

Set or clear the process-wide default Jinja environment.

**Parameters:**
- `environment` (Environment | str | os.PathLike[str] | None): A Jinja Environment instance, a path to a template directory, or None to clear the default and reset to auto-detection

##### peek_default_environment()

```python
@classmethod
def peek_default_environment() -> Environment | None
```

Return the currently configured default environment without auto-initializing.

**Returns:** The default Jinja Environment, or None if not yet configured.

#### Properties

##### environment

```python
@property
def environment() -> Environment
```

The Jinja Environment used by this renderer.

**Returns:** The Jinja Environment instance.

#### Instance Methods

##### render()

```python
def render(source: str) -> str
```

Render an HTML-like source string, expanding PascalCase component tags into HTML.

**Parameters:**
- `source` (str): HTML-like string containing component tags to render

**Returns:** The fully rendered HTML string with all components expanded.

##### new_session()

```python
def new_session() -> RenderSession
```

Create a new render session for tracking assets during rendering.

**Returns:** A fresh RenderSession instance.

## AssetMode

```python
class AssetMode(str, Enum):
    INLINE = "inline"
    NONE = "none"
```

## RenderSession

Per-render state for asset aggregation and deduplication.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `assets` | `list[CollectedAsset]` | Ordered, deduplicated asset paths collected during rendering |
| `collected_paths` | `set[str]` | Normalized paths already processed |
| `scripts` | `list[str]` | Inline JavaScript payloads (`AssetMode.INLINE` only) |
| `styles` | `list[str]` | Inline CSS payloads (`AssetMode.INLINE` only) |
| `runtime_injected` | `bool` | Whether the pyjinhx client runtime was scheduled |

### Methods

##### manifest()

```python
def manifest(*, resolver: AssetUrlResolver) -> AssetManifest
```

Return resolved stylesheet and script URLs for assets collected in this session.
