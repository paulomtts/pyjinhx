# Creating Components

Components are the building blocks of your UI. Each component is a Python class paired with a Jinja2 template.

## Basic Component

A component has two parts:

### 1. Python Class

```python
from pyjinhx import BaseComponent


class Card(BaseComponent):
    id: str              # Required - unique identifier
    title: str           # Required field
    subtitle: str = ""   # Optional with default
```

`BaseComponent` also provides `js` and `css` fields (lists of extra asset paths) — see [Asset Collection](assets.md).

### 2. HTML Template

PyJinHX uses **Jinja2** templates for its components:

```html
<!-- card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    {% if subtitle %}
        <p class="subtitle">{{ subtitle }}</p>
    {% endif %}
</div>
```

!!! tip "You can use PascalCase components inside templates"
    You can even use PascalCase components as custom tags **inside your component templates**. This lets you compose components by nesting, like `<Button .../>` or `<UserCard>...</UserCard>`, directly within other templates. PyJinHx will automatically discover and render them as components.


## The `id` Field

`id` is **auto-generated** (`pjx-<n>`) when omitted. Pass an explicit id for stable hooks (CSS selectors, htmx targets, reactive OOB targeting):

```python
button = Button(id="submit", text="Submit")  # explicit — stable hook
button = Button(text="Submit")               # auto-generated pjx-<n>
```

!!! tip "Using your own id scheme"
    Override `id` with a `default_factory` to apply your own generation strategy — for example a UUID:

    ```python
    import uuid
    from pyjinhx import BaseComponent
    from pydantic import Field

    class MyComponent(BaseComponent):
        id: str = Field(default_factory=lambda: str(uuid.uuid4()))
        # ... other fields ...
    ```

    A subclass that redeclares `id: str` **without** a default makes it required at instantiation time.


!!! tip "Auto-generated IDs apply to PascalCase tags only"
    `auto_id` does **not** affect plain Python instances — omitting `id` on `BaseComponent(...)` falls back to the built-in `pjx-<n>` counter. The `Renderer`'s `auto_id=True` only generates an `id` when a PascalCase `<Tag/>` is expanded in a template without one (see [PascalCase Tags](tags.md)). Separately, `ReactiveComponent` (not `BaseComponent`) defaults its `id` to the kebab-cased class name (e.g. `TodoCounter` → `"todo-counter"`).


## Template Discovery

Templates are automatically discovered based on the class name:

| Class Name | Template File |
|------------|---------------|
| `Button` | `button.html` or `button.jinja` |
| `ActionButton` | `action_button.html`, `action-button.html`, or `.jinja` variants |
| `UserCard` | `user_card.html`, `user-card.html`, or `.jinja` variants |

!!! warning "Template Location Requirement"
    Templates must be in the same directory as the Python class file.

A subclass with no adjacent template inherits the nearest ancestor's template and class
assets, each resolved independently (first found per kind walking the MRO). At most one
component base per class — a definition-time `TypeError` is raised if two component bases
appear in `__bases__`. Framework bases (`ReactiveComponent`) don't count toward that
limit, so `class LiveBadge(ReactiveComponent, PJXBadge, react={...})` is valid.

## Single-root rule

Every component template must render exactly **one** top-level HTML element. Rendering a
template with zero or two or more sibling top-level elements raises a `ValueError`:

```html
<!-- WRONG: two siblings at the top level -->
<h2>{{ title }}</h2>
<p>{{ body }}</p>

<!-- RIGHT: wrap them in a single root -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <p>{{ body }}</p>
</div>
```

Conditional roots are fine — the check runs on the rendered output, so any branch that
resolves to a single element passes:

```jinja
{% if href %}<a href="{{ href }}">{{ label }}</a>{% else %}<button>{{ label }}</button>{% endif %}
```

## Attribute pass-through

Inline tag attributes that are not declared fields of a component are automatically injected
onto that component's root element at render time. No template boilerplate is needed — you
don't place any special token in the template.

```python
class Card(BaseComponent):
    id: str
    title: str          # declared field — consumed as a prop, NOT injected
    subtitle: str = ""  # declared field — consumed as a prop, NOT injected
```

```html
<!-- hx-get and data-section are not Card fields, so they land on the root <div> -->
<Card id="orders" title="Orders" hx-get="/orders" hx-trigger="every 5s" data-section="main"/>
```

**Override semantics:** a stray inline attribute replaces any same-named attribute the template
already hardcodes on its root, including `class` and `style` (full replace, not merge). Attributes
that don't collide are added to the root element alongside the existing ones.

**Props vs. pass-through:** declared fields are props — they fill the template context and are
not injected. Non-declared ("stray") attributes and the explicit `extra_attrs` dict are
injected. For template-only components (no Python class, or created with `component()`), all
attributes inject onto the root and are also available as template variables.

## HTML-only components

A component doesn't always need a Python class. If you have a template with no
behaviour or typed fields — just markup — you can reference it from Python with
the `component()` factory instead of hand-writing a `BaseComponent` subclass:

```python
from pyjinhx import component

Card = component("Card")                   # finds card.html under the default environment
Card(title="Hi", content="body").render()
```

`component("Card")` returns a registered `BaseComponent` subclass bound to
`card.html`, resolved by scanning the default environment (set it via
`setup(components_root=...)` or `Renderer.set_default_environment(...)`). The
result is a first-class component: instantiate it, pass it as a field of another
component, or use `<Card/>` in a template — they all resolve to the same class.
It's idempotent and never shadows a component you've actually declared. See
[`component()`](../api/base-component.md#component).

## Prop headers for classless components

A template-only component can declare its props in a `{#def ... #}` header — the
first thing in the file. pyjinhx parses it into a validated pydantic model, so a
classless component gets defaults, required-checks, and type coercion without a
Python class:

    {#def title: str, count: int = 0, variant: str = "primary" #}
    <article class="pjx-card pjx-card--{{ variant }}">
      <h3>{{ title }}</h3>
      <span class="badge">{{ count }}</span>
      <div>{{ content }}</div>
    </article>

- The signature is Python-style: `name`, `name: type`, `name = default`, or
  `name: type = default`. A prop with no default is **required**.
- Supported types: `str`, `int`, `float`, `bool`, `list`, `dict`, and `T | None`;
  anything else (or no annotation) is treated as `Any` (no coercion).
- Declared props are validated (`<Card/>` with a missing required prop, or a
  value that can't coerce, raises a clear error). **Undeclared** attributes still
  pass through to the root element (`hx-*`, `data-*`, `@click`, `class`).
- The header is a normal Jinja comment, so it never appears in the output.
- A hand-written Python class always takes precedence over a header.

On the `component()` factory, the header is applied when the template is
resolvable at call time (set the default environment first); the `<Tag/>` path
always applies it.

## Extra Fields

A plain Pydantic `BaseModel` rejects unknown fields with a `ValidationError`. With `BaseComponent`, **extra fields are accepted and available in the template context**. This allows you to pass dictionaries or data objects with additional fields without raising validation errors.

```python
from pyjinhx import BaseComponent

class Example(BaseComponent):
    foo: int

ex = Example(foo=1, bar=2)  # No error! 'bar' is just ignored
```