# BaseComponent

Base class for defining reusable UI components with Pydantic validation and Jinja2 templating.

## Class

### BaseComponent

Subclasses are automatically registered and can be rendered using their corresponding HTML/Jinja templates. Components support nested composition, automatic JavaScript and CSS collection, and can be used directly in Jinja templates via the `__html__` protocol.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | Yes | - | Unique identifier for the component instance |
| `js` | `list[str]` | No | `[]` | Paths to additional JavaScript files to include when rendering |
| `css` | `list[str]` | No | `[]` | Paths to additional CSS files to include when rendering |

Components accept extra fields beyond those defined in the class (`extra="allow"`). Extra fields are included in the template context alongside declared fields.

#### Methods

##### render()

```python
def render(
    *,
    dirtied: set[ReactiveKey] | None = None,
    mounted: object | None = None,
    client: object | None = None,
) -> Markup
```

Render this component to HTML using its associated Jinja template.

The template is auto-discovered based on the component class name (e.g., `MyButton` looks for `my_button.html` or `my_button.jinja`). All component fields are available in the template context, and nested components are rendered recursively.

With no arguments this is a plain render. Passing `dirtied` and/or `mounted` opts into dependency-aware reactivity: this component is the primary response, and OOB swaps are appended for other mounted reactive regions whose `reacts_to` intersects `dirtied`. See [Reactivity](../reactivity.md).

| Parameter | Description |
|-----------|-------------|
| `dirtied` | State keys the route mutated (e.g. `{"todos"}`). Defaults to the primary's `reacts_to`. |
| `mounted` | Client manifest — request-like object, raw `X-PJX-Mounted` string, or parsed list. When omitted, uses the request-scoped `ClientBackend` after mutations. |
| `client` | Request-like object or raw `X-PJX-Assets` JSON for REFERENCE-mode asset dedup on root renders. When omitted, uses the request-scoped `ClientBackend`. |

**Returns:** The rendered HTML as a Markup object (safe for direct use in templates).

##### __html__()

```python
def __html__() -> Markup
```

Render the component when used in a Jinja template context.

Enables cleaner template syntax: `{{ component }}` instead of `{{ component.render() }}`.

**Returns:** The rendered HTML as a Markup object.

## NestedComponentWrapper

A wrapper for nested components. Enables access to the component's properties and rendered HTML.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `html` | `str` | The rendered HTML string of the nested component |
| `props` | `BaseComponent \| None` | The original component instance, or None for template-only components |

### Methods

##### __str__()

```python
def __str__() -> Markup
```

Returns the rendered HTML when the wrapper is used in a template context.
