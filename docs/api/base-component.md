# BaseComponent

Base class for defining reusable UI components with Pydantic validation and Jinja2 templating.

## Class

### BaseComponent

Subclasses are automatically registered and can be rendered using their corresponding HTML/Jinja templates. Components support nested composition, automatic JavaScript collection, and can be used directly in Jinja templates via the `__html__` protocol.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | Yes | - | Unique identifier for the component instance |
| `js` | `list[str]` | No | `[]` | Paths to additional JavaScript files to include when rendering |

#### Special Fields

These fields are automatically injected by PyJinHx in specific contexts:

| Field | Type | When Available | Description |
|-------|------|---------------|-------------|
| `content` | `str` | Template-side rendering with children | Inner HTML of component tags. Example: `<Card>text</Card>` makes `content="text"` available in the template |

#### Extra Fields

Components accept extra fields beyond those defined in the class. Extra fields are stored by Pydantic and passed through to the template context, making them available for use in templates.

#### Methods

##### render()

```python
def render() -> Markup
```

Render this component to HTML using its associated Jinja template.

The template is auto-discovered based on the component class name (e.g., `MyButton` looks for `my_button.html` or `my_button.jinja`). All component fields are available in the template context, and nested components are rendered recursively.

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

!!! note "Automatic Usage"
    `NestedComponentWrapper` is created automatically during rendering. You don't import or instantiate it directly.

    Access nested component properties in templates using `.props`:

    ```html
    <!-- Render the component's HTML -->
    {{ nested_component }}

    <!-- Access the component's properties -->
    {{ nested_component.props.id }}
    {{ nested_component.props.text }}
    ```

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
