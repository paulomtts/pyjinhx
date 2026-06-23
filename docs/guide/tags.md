# PascalCase Tags

## What are PascalCase tags?

In PyJinHx, **PascalCase tags** are custom component tags used inside HTML strings or templates. They are identified by their tag name being PascalCase (e.g. `<Button/>`, `<UserCard/>`), and are rendered as components rather than plain HTML.

```python
from pyjinhx import Renderer

renderer = Renderer.get_default_renderer()
html = renderer.render('<UserCard name="Ada"/>')
```

You can also use PascalCase tags **inside component templates** to compose components declaratively.

!!! warning "Recognized tag names are strict PascalCase"
    A tag is treated as a component only if its name matches `^[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*)?$` — a capital letter followed by alternating lowercase/Capitalized words. This **rejects acronyms and trailing digits**: `UI`, `APIKey`, `HTMLBlock`, `Button2`, and `H2` are NOT recognized and pass through as raw HTML. Name components like `Api`, `ApiKey`, or `HtmlBlock` instead.

## Attributes

Tag attributes become template context variables. For components with a `BaseComponent`
subclass, declared fields are consumed as props (Pydantic-validated and available in the
template). Non-declared ("stray") attributes are injected onto the component's root
element automatically — no template token needed.

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

Stray attributes like `hx-*`, `data-*`, or `aria-*` passed on any PascalCase tag land
on the root element of that component with **override semantics** — an inline attribute
replaces any same-named attribute the template hardcodes, including `class` and `style`.
See [Creating Components](components.md#attribute-pass-through) for the full rules.

## The `content` Variable

Inner content of a tag becomes the `{{ content }}` template variable:

```python
html = renderer.render("""
    <Card title="Note">
        This text becomes the content variable.
    </Card>
""")
```

`content` is **always** passed to a tag-instantiated component, defaulting to `""` when the tag has no inner content. (A `BaseComponent` accepts it as an extra field; declare `content: str` on your class if you want validation.)

## Template Auto-Discovery

PascalCase tag names are converted to candidate template filenames in this order:

1. `snake_case.pjx`
2. `kebab-case.pjx`
3. `snake_case.html`
4. `kebab-case.html`
5. `snake_case.jinja`
6. `kebab-case.jinja`

For example, `<ActionButton/>` searches for: `action_button.pjx`, `action-button.pjx`, `action_button.html`, `action-button.html`, `action_button.jinja`, `action-button.jinja`.

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
html = renderer.render('<Hint kind="warning">Be careful</Hint>')
```

!!! note "Builtins are not auto-discovered"
    The fallback only searches under your Jinja loader root, so it does **not** cover [built-in components](../components.md) — their templates ship inside the pyjinhx package. Using `<PJXTooltip/>` (or any builtin) as a tag requires importing it once at startup (`from pyjinhx.builtins import PJXTooltip` or `import pyjinhx.builtins`), which registers the class. Otherwise rendering raises a `FileNotFoundError` telling you which import to add.

The generic-fallback instance is **removed from the registry** after rendering, so it cannot be cross-referenced by other templates (unlike a registered-class instance).

## Auto-Generated IDs

When `auto_id=True` (default), IDs are generated automatically if not provided in the tag. Disable this with:

```python
renderer = Renderer.get_default_renderer(auto_id=False)
```

## Parser API

For programmatic access to the parse tree (without rendering), use `Parser` and `Tag` directly. See [Parser & Tag](../api/parser.md).

## See next

- [Nesting](nesting.md) - Compose components together
- [Asset Collection](assets.md) - Automatic JS and CSS handling
- [Public API Index](../reference/public-api.md) - Full export reference
