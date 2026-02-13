# PascalCase Tags

## What are PascalCase tags?

In PyJinHx, **PascalCase tags** are custom component tags used inside HTML strings or templates. They are identified by their tag name being PascalCase (e.g. `<Button/>`, `<UserCard/>`), and are rendered as components rather than plain HTML.

```python
from pyjinhx import Renderer

renderer = Renderer.get_default_renderer()
html = renderer.render('<UserCard name="Ada"/>')
```

You can also use PascalCase tags **inside component templates** to compose components declaratively.

## Attributes

Tag attributes become template context variables:

```python
html = renderer.render('''
    <Input
        type="email"
        name="user_email"
        placeholder="Enter your email"
        required="true"
    />
''')
```

## The `content` Variable

Inner content of a tag becomes the `{{ content }}` template variable:

```python
html = renderer.render("""
    <Card title="Note">
        This text becomes the content variable.
    </Card>
""")
```

## Template Auto-Discovery

PascalCase tag names are converted to candidate template filenames in this order:

1. `snake_case.html`
2. `kebab-case.html`
3. `snake_case.jinja`
4. `kebab-case.jinja`

For example, `<ActionButton/>` searches for: `action_button.html`, `action-button.html`, `action_button.jinja`, `action-button.jinja`.

Templates are searched under the root directory of your Jinja `FileSystemLoader` (see [Configuration](configuration.md)).

## Component Resolution

When PyJinHx encounters a PascalCase tag, it resolves the component in this order:

### 1. Registered instance (highest priority)

If the tag's `id` matches a pre-registered component instance, that instance is reused and its properties are updated with the tag's attributes.

```python
from pyjinhx import BaseComponent, Renderer

class Button(BaseComponent):
    id: str
    text: str = "default"
    variant: str = "primary"

# Create and register an instance
btn = Button(id="my-btn", text="Original", variant="danger")

# Render via tag — uses existing instance, updates 'text'
renderer = Renderer.get_default_renderer()
html = renderer.render('<Button id="my-btn" text="Updated"/>')
# Result uses variant="danger" (from instance) and text="Updated" (from tag)
```

!!! warning "Type validation"
    The tag name must match the instance's class name. A `TypeError` is raised if they don't match.

### 2. Registered class

If a `BaseComponent` subclass with a matching name exists, PyJinHx instantiates it — giving you Pydantic validation, defaults, and field types.

```python
class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"

renderer = Renderer.get_default_renderer()
html = renderer.render('<Button text="Save"/>')  # Validated using Button
```

### 3. Generic fallback

If no class is registered, PyJinHx falls back to a generic `BaseComponent` and renders using the auto-discovered template. All tag attributes become template context variables. No Pydantic validation is applied.

```python
html = renderer.render('<Alert kind="warning">Be careful</Alert>')
```

## Auto-Generated IDs

When `auto_id=True` (default), IDs are generated automatically if not provided in the tag. Disable this with:

```python
renderer = Renderer.get_default_renderer(auto_id=False)
```

## See next

- [Nesting](nesting.md) - Compose components together
- [Asset Collection](assets.md) - Automatic JS and CSS handling
