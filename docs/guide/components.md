# Creating Components

Components are the building blocks of your UI. Each component is a Python class paired with a Jinja2 template.

## Basic Component

A component has two parts:

### 1. Python Class

```python
from pyjinhx import BaseComponent


class Card(BaseComponent):
    id: str  # Required - unique identifier
    title: str  # Required field
    subtitle: str = ""  # Optional with default
```

Extra CSS/JS assets are auto-discovered from adjacent `.css`/`.js` files sharing the component's snake_case stem — the same stem as its template, so `Card` picks up `card.css` and `card.js` — see [Asset Collection](assets.md) — not declared as fields on the class.

### 2. HTML Template

PyJinHX uses **Jinja2** templates for its components:

```html
<!-- card.pjx -->
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
button = Button(text="Submit")  # auto-generated pjx-<n>
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


!!! tip "Turning auto-ids off"
    Set the `auto_id` class var to `False` to make `id` mandatory for that component — the `pjx-<n>` fallback is disabled and omitting `id` fails validation, whether you instantiate it from Python or write `<Tag/>` in a template (see [PascalCase Tags](tags.md)).

!!! warning "Reactive components need an explicit `id`"
    `ReactiveComponent` declares no `id` of its own, so it inherits the same `pjx-<n>` fallback — and that value is **not** stable across renders. A reactive region has to stay addressable for out-of-band swaps to find it, so always pass an explicit, stable `id=` (e.g. `TodoCounter(id="todo-counter")`).


## Template Discovery

Templates are automatically discovered based on the class name, which is converted to
snake_case and given the `.pjx` extension. That is the only naming convention there is —
no `.html`/`.jinja` fallbacks, and no kebab-case:

| Class Name | Template File |
|------------|---------------|
| `Button` | `button.pjx` |
| `ActionButton` | `action_button.pjx` |
| `UserCard` | `user_card.pjx` |

!!! warning "Template Location Requirement"
    Templates must be in the same directory as the Python class file.

A subclass with no adjacent template inherits the nearest ancestor's template and class
assets, each resolved independently (first found per kind walking the MRO). Mixing a
framework base with a component base works the same way — `class LiveBadge(ReactiveComponent,
PJXBadge, react={...})` renders `pjx_badge.pjx`, the nearest template on the MRO.

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

Every inline tag attribute becomes a constructor argument of the component class, so on a
declared component each attribute must be a **declared field**. There is no automatic
injection of stray attributes onto the root element: an attribute the class doesn't declare
is a `ValidationError`, not a pass-through.

```python
class Card(BaseComponent):
    id: str
    title: str  # declared field — fills the template context
    subtitle: str = ""  # declared field — fills the template context
```

```html
<!-- ValidationError: hx-get is not a Card field -->
<Card id="orders" title="Orders" hx-get="/orders"/>
```

To let a component carry arbitrary `hx-*` / `data-*` attributes, declare a field for them and
emit it on the root yourself — this is what the built-in UI components do with their
`extra_attrs` dict:

```python
from pydantic import Field


class Card(BaseComponent):
    id: str
    title: str
    extra_attrs: dict[str, str] = Field(default_factory=dict)
```

```jinja
<div id="{{ id }}"{% for name, value in extra_attrs.items() %} {{ name }}="{{ value }}"{% endfor %}>
    <h2>{{ title }}</h2>
</div>
```

```html
<Card id="orders" title="Orders" extra_attrs='{"hx-get": "/orders", "hx-trigger": "every 5s"}'/>
```

Template-only components (no Python class, or created with `component()`) are the loose case:
they accept undeclared attributes and expose them as template variables, so you decide where —
and whether — they land in the markup.

## Escaping and slots

Template output is **HTML-escaped by default**. pyjinhx runs Jinja with
`autoescape=True`, so the special characters `& < > " '` in a value are turned
into entities (`&amp; &lt; &gt; &#34; &#39;`) before they reach the page. This is
the safe default: a scalar prop, text, an attribute value, or a value derived in
a `{% for %}` loop is escaped, so user-supplied data can't inject markup or break
out of an attribute.

```python
PJXCardHeader(id="c", title="<script>alert(1)</script>")
# title renders as &lt;script&gt;alert(1)&lt;/script&gt; — not executable
```

**What renders as raw HTML (not escaped):**

- A component's **children**/`content` field (the `_pjx_children_field`, e.g.
  `PJXCardBody.content`) — its string value is emitted verbatim.
- Any field declared `Slot` (`from pyjinhx import Slot`). A `Slot` field is
  `str | BaseComponent`; its string value renders raw. `Slot` collections work
  too — string elements inside a `Slot`-annotated `list`/`dict` (e.g.
  `PJXDropdown.items`) render raw.
- Any **`BaseComponent`** value — a nested component always renders its own HTML
  raw via the `__html__` protocol, whether passed directly or inside a list/dict.

```python
# content is the children field → raw HTML
PJXCardBody(id="c", content="<p data-x='1'>hi</p>")
# renders <p data-x='1'>hi</p> verbatim
```

**Escape hatches** — when you trust the markup and want it raw in a *scalar*
field, choose one:

- Declare the field as `Slot` (`field: Slot = ""`).
- Mark it safe in the template: `{{ value|safe }}`.
- Pass a `BaseComponent` instance — it renders raw via `__html__`.

> Raw HTML is only as safe as its source. Reserve slots / `|safe` / nested
> components for markup you control; never pass unsanitized user input raw.

Prop-header props (`{#def ... #}`, below) follow the same rule: a header-declared
prop is **escaped** unless you mark it safe in the template (`{{ prop|safe }}`) or
the prop is the component's children field. Header props can't be typed `Slot`
directly, so use `|safe` for intentional raw HTML there.

## HTML-only components

A component doesn't always need a Python class. If you have a template with no
behaviour or typed fields — just markup — you can reference it from Python with
the `component()` factory instead of hand-writing a `BaseComponent` subclass:

```python
from pyjinhx import component

Card = component("Card")  # finds card.pjx under the default environment
Card(title="Hi", content="body").render()
```

`component(name, template_dir=None)` returns a registered `BaseComponent` subclass
bound to the discovered template (`card.pjx` for `"Card"`). By default it resolves the
template the same way tag rendering does — under the directory `setup(components_root=...)`
last registered — but you can pass `template_dir` explicitly to point at a different
directory instead. The result is a first-class component: instantiate it, pass it as a field
of another component, or use `<Card/>` in a template — they all resolve to the same class.
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
  value that can't coerce, raises a clear error). **Undeclared** attributes are
  still accepted rather than rejected (`hx-*`, `data-*`, `@click`, `class`) and
  reach the template context — nothing places them in the markup for you.
- The header is a normal Jinja comment, so it never appears in the output.
- Header-declared props are **HTML-escaped** like any scalar value (see
  [Escaping & slots](#escaping-and-slots)). For intentional raw HTML, mark it safe
  in the template with `{{ prop|safe }}` — header props can't be typed `Slot`.
- A hand-written Python class always takes precedence over a header.

The header is read when the class is built, so `component()` needs the template
to be resolvable at call time — pass `template_dir`, or run
`setup(components_root=...)` first. Discovery deliberately leaves an orphan
`.pjx` unregistered, so materialize it with `component()` once before using
`<Tag/>` for it in another template.

## Extra Fields

`BaseComponent` is **strict**: like a plain Pydantic `BaseModel`, it rejects unknown keyword
arguments with a `ValidationError`. Every prop a component accepts from Python has to be a
declared field.

```python
from pyjinhx import BaseComponent


class Example(BaseComponent):
    foo: int


Example(foo=1, bar=2)  # ValidationError: Extra inputs are not permitted
```

Classless components are the exception. A component built from a template — by
`component()` or by a `{#def #}` header — is generated with `extra="allow"`, so it
accepts undeclared keys and makes them available in the template context. That is what
lets `hx-*`, `data-*` and other stray attributes pass through to the root element (see
[Attribute pass-through](#attribute-pass-through)).

A hand-written class can opt into the same thing with pydantic's own config — there is no
pyjinhx-specific base to import:

```python
from pydantic import ConfigDict
from pyjinhx import BaseComponent


class Card(BaseComponent):
    model_config = ConfigDict(extra="allow")
    title: str = ""
```