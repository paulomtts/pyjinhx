# BaseComponent

Base class for defining reusable UI components with Pydantic validation and Jinja2 templating.

## Class

### BaseComponent

Subclasses are automatically registered and can be rendered using their corresponding HTML/Jinja templates. Components support nested composition, automatic JavaScript and CSS collection, and can be used directly in Jinja templates via the `__html__` protocol.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | No | auto-generated (`pjx-<n>`) when omitted | Unique identifier for the component instance |
| `js` | `list[str]` | No | `[]` | Paths to additional JavaScript files to include when rendering |
| `css` | `list[str]` | No | `[]` | Paths to additional CSS files to include when rendering |

Components accept extra fields beyond those defined in the class (`extra="allow"`). Extra fields are included in the template context alongside declared fields.

#### Methods

##### render()

```python
def render() -> Markup
```

Render this component to HTML using its associated Jinja template.

The template is auto-discovered based on the component class name (e.g., `MyButton` looks for `my_button.html` or `my_button.jinja`). All component fields are available in the template context, and nested components are rendered recursively. Subclasses with no adjacent template inherit the nearest ancestor's template and assets through the MRO (first found per kind); a class may have at most one concrete component base — multiple concrete bases raise `TypeError` at definition time (see [Component guide](../guide/components.md)).

This is a plain, zero-argument render. The dependency-aware reactive behavior (`dirtied` / `mounted` / `client`) lives on `ReactiveComponent` — see [Reactive API](reactive-api.md).

**Returns:** The rendered HTML as a Markup object (safe for direct use in templates).

##### __html__()

```python
def __html__() -> Markup
```

Render the component when used in a Jinja template context.

Enables cleaner template syntax: `{{ component }}` instead of `{{ component.render() }}`.

**Returns:** The rendered HTML as a Markup object.

## component

```python
def component(name: str) -> type[BaseComponent]
```

Reference an **html-only** component — a template that has no hand-written Python class — from Python. Returns a `BaseComponent` subclass bound to that template, so you can instantiate, nest, and render it like any declared component.

```python
from pyjinhx import component

Card = component("Card")                  # finds card.html under the default environment
Card(title="Hi", content="body").render()
```

The template is resolved by **scanning the default environment** by tag name (`card.html`/`card.jinja`), the same lookup used for `<Card/>` tags in templates — so set the default environment first (e.g. `setup(components_root=...)` or `Renderer.set_default_environment(...)`). Resolution is lazy: `component("Card")` works even before the environment is set; the template is located at render time.

Arbitrary attributes are accepted (`extra="allow"`) and children map to the `content` slot, e.g. `component("Card")(title="Hi", content="body")`.

- **`name`** must be PascalCase (so it round-trips as `<Name/>` in templates) — otherwise `ValueError`.
- **Idempotent and non-shadowing:** if a class is already registered under `name` (previously synthesized, or a real declared component), that class is returned — `component("Card")` twice returns the same object, and it never replaces a declared component.
- A missing template raises `FileNotFoundError` at render time.

Because the returned class is registered, it also resolves as `<Card/>` inside other templates.

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
def __str__() -> str
```

Returns the wrapper's `html` field (a plain string) when used in a template context.
