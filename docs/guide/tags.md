# PascalCase Components

## What are PascalCase components?

In PyJinHx, **PascalCase components** are custom component tags used inside HTML to refer to a component template at render time.

They are identified purely by their tag name being **PascalCase** (e.g. `<Button/>`, `<UserCard/>`, `<NavBar>...</NavBar>`), and are treated as *components* rather than plain HTML.

Example:

```html
<UserCard name="Ada"/>
```

## Template Auto-Discovery

Once a tag is considered a component, PyJinHx attempts **template auto-discovery**:

- The tag name is converted from PascalCase to `snake_case`
- Candidate template filenames are tried in order: `snake_case_name.html` then `snake_case_name.jinja`

For example:

- `<ActionButton/>` → `action_button.html` → `action_button.jinja`

Templates are searched under the **root directory of your Jinja `FileSystemLoader`** (see [Configuration](configuration.md)).

Example:

```text
<UserCard/>  ->  user_card.html  ->  user_card.jinja
```

## Component Resolution Priority

When PyJinHx finds a PascalCase tag, it resolves the component in this order:

1. **Registered instance** — If the tag's `id` matches an existing registered instance
2. **Registered class** — If the tag name matches a registered `BaseComponent` subclass
3. **Generic fallback** — Use `BaseComponent` with the auto-discovered template

### Registered instance (highest priority)

If a tag has an `id` attribute that matches a pre-registered component instance, PyJinHx uses that existing instance instead of creating a new one. The instance's properties are updated with any attributes from the tag.

This is useful when you want to pre-configure a component in Python and then render it via a tag:

```python
from pyjinhx import BaseComponent, Renderer


class Button(BaseComponent):
    id: str
    text: str = "default"
    variant: str = "primary"


# Create and register an instance
btn = Button(id="my-btn", text="Original", variant="danger")

# Render via tag - uses existing instance, updates 'text' attribute
renderer = Renderer.get_default_renderer()
html = renderer.render('<Button id="my-btn" text="Updated"/>')
# Result uses variant="danger" (from instance) and text="Updated" (from tag)
```

!!! warning "Type validation"
    The tag name must match the instance's class name. A `TypeError` is raised if they don't match:

    ```python
    class ButtonA(BaseComponent):
        id: str

    btn = ButtonA(id="shared-id")

    # This raises TypeError: Tag <ButtonB> references instance 'shared-id' which is of type ButtonA
    renderer.render('<ButtonB id="shared-id"/>')
    ```

### Registered class (preferred for new instances)

If there is a registered `BaseComponent` subclass whose class name matches the tag (e.g. `class Button(BaseComponent)` for `<Button/>`), PyJinHx instantiates a new instance of that class.

That means you get:

- Pydantic validation
- Defaults and field types
- Your component's rendering behavior

Example:

```python
from pyjinhx import BaseComponent, Renderer


class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"


renderer = Renderer.get_default_renderer()
html = renderer.render('<Button text="Save"/>') # Will be validated using Button before rendering
```

### Generic fallback

If **no class is registered** for the tag name, PyJinHx falls back to a **generic `BaseComponent`** instance and renders it using the auto-discovered template.

In this mode:

- All tag attributes become template context variables
- The inner HTML becomes `{{ content }}`

Example:

```python
from pyjinhx import Renderer

renderer = Renderer.get_default_renderer()
html = renderer.render('<Alert kind="warning">Be careful</Alert>') # No validation
```

## Example

Assume you have a registered component class `Button` and a template named `button.html`.

```html
<button id="{{ id }}">{{ text }}</button>
```

```python
from pyjinhx import BaseComponent, Renderer


class Button(BaseComponent):
    id: str
    text: str


renderer = Renderer.get_default_renderer()
html = renderer.render('<Button text="Click me"/>')
```

Because the tag is PascalCase:

- `<Button .../>` is treated as a component tag
- `button.html` / `button.jinja` is auto-discovered
- If `auto_id=True` (default), an `id` is generated when not provided

## See next

Next, see [Rendering](rendering.md) for:

- Nested PascalCase components
- The `content` variable
- Auto-generated IDs
