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

## Registered vs. Generic Components

When PyJinHx finds a PascalCase tag, it chooses how to build the component instance:

### Registered model (preferred)

If there is a registered `BaseComponent` subclass whose class name matches the tag (e.g. `class Button(BaseComponent)` for `<Button/>`), PyJinHx instantiates that class.

That means you get:

- Pydantic validation
- Defaults and field types
- Your component’s rendering behavior

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

### Generic model (fallback)

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

Next, see [Template Rendering](template-rendering.md) for:

- Nested PascalCase components
- The `content` variable
- Auto-generated IDs
