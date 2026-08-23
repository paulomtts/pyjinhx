# Render

Rendering pipeline used by `BaseComponent.render()` and the free `render()` function: turns a component instance into a finished HTML string, expanding nested PascalCase tags and collecting JavaScript/CSS along the way.

## render()

```python
def render(component: BaseComponent, session: RenderSession | None = None) -> str
```

Render a component to a final HTML string. Thin wrapper closing the loop for a top-level component: `render_level()` produces the component's `RenderedLevel`, which is then serialized back into markup.

`session` defaults to a fresh `RenderSession()` when omitted, so callers outside the kernel don't need to construct one by hand.

Fires each `session.on_rendered` callback with `(component, level, session)` after each component's level is built, depth-first post-order.

**Returns:** The component's rendered markup as a finished HTML string, with the session's accumulated assets appended per their delivery mode.

**Raises:**

- `ValueError` — if a template renders zero or 2+ root elements, or a call chain repeats the same class past the cycle limit.
- `jinja2.TemplateNotFound` — if the template file is missing.
- `jinja2.TemplateAssertionError` — if Jinja evaluation fails.

## render_level()

```python
def render_level(
    component: BaseComponent,
    session: RenderSession,
    chain: tuple[str, ...] = (),
) -> RenderedLevel
```

Render one component level: template → single parse → `RenderedLevel`. Internal/recursive callers use this directly (they need the `RenderedLevel`, not a string); `render()` is the public, string-returning wrapper for a childless call site.

`chain` carries the class names already being rendered on the current call path, outermost first — used to detect a call path that has stopped making progress (the same class recurring past a repeat limit), not merely reused at different depths.

## RenderSession

Per-render state: the Jinja environment, asset accumulation, parsed pjx request headers, and render-completion hooks. It takes no arguments and carries no components root: its loader is `AbsolutePathLoader`, which resolves each template name as an absolute filesystem path, because template paths are already fully resolved per class before Jinja sees them. The root that discovery walks is set once with `setup(components_root=...)`.

```python
def __init__(self) -> None
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `jinja_env` | `Environment` | The Jinja environment used for this render, autoescape enabled |
| `asset_paths` | `set[str]` | Generic per-request asset slot; no producer writes to it yet |
| `css_assets` | `set[Path]` | CSS descriptor paths accumulated as components render |
| `js_assets` | `set[Path]` | JS descriptor paths accumulated as components render |
| `css_mode` | `AssetMode` | CSS delivery mode for this render (`INLINE` by default) |
| `js_mode` | `AssetMode` | JS delivery mode for this render (`INLINE` by default) |
| `runtime_script` | `str \| None` | The pyjinhx client runtime payload, set by `client/inject.py` |
| `runtime_style` | `str \| None` | The runtime's CSS block, emitted alongside the other `<style>` tags |
| `runtime_injected` | `bool` | Whether the client runtime was already scheduled for this session |
| `on_rendered` | `list[Callable[[BaseComponent, RenderedLevel, RenderSession], None]]` | Hooks fired once per component after its subtree finishes rendering |
| `pjx_request` | `Any` | The Starlette request bound to this render, set by middleware |
| `pjx_mounted` | `list[dict[str, Any]]` | The client's parsed `X-PJX-Mounted` manifest, set by middleware and read by fan-out |
| `pjx_assets` | `frozenset[str]` | The client's parsed `X-PJX-Assets` tokens — which assets it already holds |
| `pjx_trigger` | `dict[str, Any] \| None` | The parsed htmx trigger header for this request, or `None` |
| `nested_react_keys` | `dict[str, tuple[str, ...]]` | Reactive instance id → that class's reactive keys, written by `record_nested_react_keys` when a caller appends it to `on_rendered` |

The three `pjx_*` manifest fields live on the session rather than on `request.state` because the response composer is framework-free: it has no `Request` to read them from.

### emit_rendered()

```python
def emit_rendered(self, component: BaseComponent, level: RenderedLevel) -> None
```

Notify subscribers (`on_rendered`) that `component`'s subtree finished rendering. Called once per component, bottom-up, as the last step of `render_level()`; exceptions from a subscriber propagate rather than being swallowed.

## AssetMode

```python
class AssetMode(str, Enum):
    INLINE = "inline"
    NONE = "none"
    LINK = "link"
```

Per-kind (CSS/JS) delivery mode for a render. `INLINE` is the default so a cold render works with no configuration; `NONE` is how a caller shipping assets some other way (a build step, a CDN) suppresses emission; `LINK` emits a reference instead of inlining contents (`<link rel="stylesheet">` for CSS, `<script src>` for JS), requiring a URL resolver to turn each asset path into a servable URL.
