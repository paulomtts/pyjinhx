# Renderer

Shared rendering engine used by `BaseComponent` rendering and HTML-like custom-tag rendering.

## Class

### Renderer

This renderer centralizes:
- Jinja template loading (by component class or explicit file/source)
- Expansion of PascalCase custom tags inside rendered markup
- JavaScript collection/deduping and root-level script injection
- Rendering of HTML-like source strings into component output

#### Constructor

##### __init__()

```python
def __init__(
    environment: Environment,
    *,
    auto_id: bool = True,
    inline_js: bool | None = None
) -> None
```

Initialize a Renderer with the given Jinja environment.

**Parameters:**
- `environment` (Environment): The Jinja2 Environment to use for template rendering
- `auto_id` (bool): If True (default), generate UUIDs for components without explicit IDs
- `inline_js` (bool | None): If True, JavaScript is collected and injected as `<script>` tags. If False, no scripts are injected. Defaults to the class-level setting

#### Class Methods

##### get_default_renderer()

```python
@classmethod
def get_default_renderer(
    *,
    auto_id: bool = True,
    inline_js: bool | None = None
) -> Renderer
```

Return a cached default renderer instance.

**Parameters:**
- `auto_id` (bool): If True, generate UUIDs for components without explicit IDs
- `inline_js` (bool | None): If True, JavaScript is collected and injected as `<script>` tags. If False, no scripts are injected. Defaults to the class-level setting

**Returns:** A Renderer instance cached by (environment identity, auto_id, inline_js).

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

##### set_default_inline_js()

```python
@classmethod
def set_default_inline_js(inline_js: bool) -> None
```

Set the process-wide default for inline JavaScript injection.

**Parameters:**
- `inline_js` (bool): If True (default), JavaScript is collected and injected as `<script>` tags. If False, no scripts are injected. Use Finder.collect_javascript_files() for static serving.

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

PascalCase tags (e.g., `<MyButton text="OK">`) are matched to registered component classes or template files and rendered recursively. Standard HTML is passed through unchanged. Associated JavaScript files are collected and injected as a `<script>` block.

**Parameters:**
- `source` (str): HTML-like string containing component tags to render

**Returns:** The fully rendered HTML string with all components expanded.

##### new_session()

```python
def new_session() -> RenderSession
```

Create a new render session for tracking scripts during rendering.

**Returns:** A fresh RenderSession instance.

## RenderSession

Per-render state for script aggregation and deduplication.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `scripts` | `list[str]` | Collected JavaScript code snippets to inject |
| `collected_js_files` | `set[str]` | Set of JS file paths already processed (for deduplication) |
