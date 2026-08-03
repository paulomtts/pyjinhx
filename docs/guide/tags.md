# PascalCase Tags

## What are PascalCase tags?

In PyJinHx, **PascalCase tags** are custom component tags used inside a component's own
template. They are identified by their tag name being PascalCase (e.g. `<Button/>`,
`<UserCard/>`), and are expanded into the matching component's rendered HTML when the
template that contains them is rendered.

```python
from pyjinhx import BaseComponent, render


class UserCard(BaseComponent):
    id: str
    name: str


class Page(BaseComponent):
    id: str
```

```html
<!-- page.html -->
<div id="{{ id }}">
    <UserCard name="Ada"/>
</div>
```

```python
html = render(Page(id="home"))
```

A PascalCase tag resolves only after its component class has been registered — importing the
class registers it, and `setup(components_root=...)` registers every class it finds while
walking your template tree (see [Configuration](configuration.md)). For per-request isolation
in a web app, see [Component Registry](registry.md) (Advanced).

!!! warning "Recognized tag names are strict PascalCase"
    A tag is treated as a component only if its name matches `^[A-Z](?=[A-Za-z0-9]*[a-z])[A-Za-z0-9]*$` — it must start with a capital letter and contain at least one lowercase letter somewhere after it. This **rejects all-caps names**: `UI`, `H2`, and `ID` are NOT recognized and pass through as raw HTML. Names like `APIKey`, `HTMLBlock`, and `Button2` ARE recognized — the lowercase letters later in the name are enough to satisfy the pattern.

## Attributes

Tag attributes become template context variables. For components with a `BaseComponent`
subclass, declared fields are consumed as props (Pydantic-validated and available in the
template). Non-declared ("stray") attributes are injected onto the component's root
element automatically — no template token needed.

```html
<Input
    type="email"
    name="user_email"
    placeholder="Enter your email"
    required="true"
/>
```

Stray attributes like `hx-*`, `data-*`, or `aria-*` passed on any PascalCase tag land
on the root element of that component with **override semantics** — an inline attribute
replaces any same-named attribute the template hardcodes, including `class` and `style`.
See [Creating Components](components.md#attribute-pass-through) for the full rules.

### Passing lists and dicts

A tag attribute is always a plain string — the template is fully rendered before the tag is
parsed out of it. For a field typed `list`, `dict`, or a nested `BaseModel`, a JSON-looking
attribute value (starts with `{` or `[`) is parsed automatically before Pydantic sees it, so a
structured prop just works with `| tojson`:

```python
class Sources(BaseComponent):
    items: list = Field(default_factory=list)
```

```html
<Sources items='{{ items | tojson }}'/>
```

Use single quotes around the attribute — `tojson` is HTML-safe but leaves `"` unescaped. This
coercion only fires when the field's annotation is unambiguous (`list`, `dict`, a `BaseModel`
subclass, or one of those unioned with `None`); a field typed `str | list` is left as a literal
string, since a JSON-looking string there is ambiguous.

## The `content` Variable

Inner content of a tag becomes the `{{ content }}` template variable:

```html
<Card title="Note">
    This text becomes the content variable.
</Card>
```

`content` is **always** passed to a tag-instantiated component, defaulting to `""` when the tag has no inner content. (A `BaseComponent` accepts it as an extra field; declare `content: str` on your class if you want validation.)

## Template Auto-Discovery

A PascalCase tag maps to exactly one candidate filename: its `snake_case` name with a
`.pjx` extension. For example, `<ActionButton/>` resolves to `action_button.pjx`.

For an imported class, that file lives next to the module that defines it. For classes
discovered by `setup(components_root=...)`, the file is found by walking the
`components_root` tree for `.pjx` files whose stem is a valid snake_case name (see
[Configuration](configuration.md)).

## Component Resolution

When PyJinHx encounters a PascalCase tag, it resolves the component in this order:

### 1. Registered class

If a `BaseComponent` subclass with a matching name has been registered (by import, or by
`setup(components_root=...)` walking your template tree), PyJinHx builds a fresh instance of
it from the tag's attributes and inner content — giving you Pydantic validation, defaults, and
field types.

```python
class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"
```

```html
<Button text="Save"/>  <!-- validated using Button -->
```

### 2. Unregistered tag — left as-is

If no class is registered for the tag, PyJinHx does not raise and does not fall back to a
generic component: the tag is written back out exactly as it was, as ordinary markup. A
registry miss is treated as an answer, not an error — the tag may simply be a web component,
or markup nobody meant to intercept.

!!! note "Builtins are not auto-discovered"
    The registry only covers classes registered under your own template tree, so it does
    **not** cover [built-in components](../components.md) — their templates ship inside the
    pyjinhx package. Using `<PJXTooltip/>` (or any builtin) as a tag requires importing it
    once at startup (`from pyjinhx.builtins import PJXTooltip` or `import pyjinhx.builtins`),
    which registers the class. Without that import the tag is simply passed through
    unrecognized rather than expanded.

## Auto-Generated IDs

`auto_id` is a `ClassVar[bool]` on `BaseComponent`, defaulting to `True`. While true, an `id`
is generated automatically (`pjx-<n>`) for a PascalCase tag that omits one. Override it per
component class to require an explicit `id` instead:

```python
class Button(BaseComponent):
    auto_id = False
    id: str  # now required — no default is generated
    text: str
```

## See next

- [Nesting](nesting.md) - Compose components together
- [Asset Collection](assets.md) - Automatic JS and CSS handling
- [Public API Index](../reference/public-api.md) - Full export reference
