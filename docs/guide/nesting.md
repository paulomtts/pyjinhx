# Nesting

PyJinHx makes it easy to compose components together. You can nest single components, lists of components, or dictionaries of components.

!!! note "Two nesting styles, two `id` rules"
    There are two ways to nest:

    - **Python field values** (this page) — you build child instances yourself; give each child an **explicit `id`** (auto-generated `pjx-<n>` ids are not stable hooks).
    - **PascalCase `<Tag/>` in templates** (see [PascalCase Tags](tags.md)) — the renderer instantiates children for you and can **auto-generate the `id`** when `auto_id=True` (the default).

!!! info "A nested field must be declared `Slot`"
    A field only renders a `BaseComponent` value's HTML in place when it is declared `Slot`
    (or `Children`, for the component's children field — see
    [Escaping and slots](components.md#escaping-and-slots)). A plain `Button` or
    `list[Button]` annotation makes the field an ordinary Pydantic field, not a nesting point.

## Direct Nesting

Pass a component as a field value:

```python
from pyjinhx import BaseComponent, Slot


class Button(BaseComponent):
    id: str
    text: str


class Card(BaseComponent):
    id: str
    title: str
    action: Slot = ""  # nested component goes here
```

```html
<!-- card.pjx -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <div class="actions">
        {{ action }}
    </div>
</div>
```

```python
card = Card(id="hero", title="Welcome", action=Button(id="cta", text="Get Started"))
html = card.render()
```

## Nested components are opaque

A `Slot`-typed field holding a `BaseComponent` is not exposed to the template as the
component's props — only `{{ field }}` (its rendered HTML) is available. There is no
`{{ action.text }}` or similar property access: the child's own template is the only place
its fields are used, keeping the parent free to swap in whatever child it likes without the
parent template depending on the child's shape.

```html
<!-- card.pjx -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>

    <!-- Renders the component's own HTML -->
    {{ action }}
</div>
```

If a template does need to know something about the child from the parent's side (a CSS
class, a label), pass that as a separate scalar field on the parent instead of trying to reach
into the nested component.

## Lists of Components

A list of nested components also needs a `Slot`-typed field — `Slot`'s string-or-component
union works inside a `list` or `dict` too:

```python
from typing import Annotated

from pyjinhx import BaseComponent
from pyjinhx._component import PjxSlot


class ButtonGroup(BaseComponent):
    id: str
    buttons: Annotated[list[str | Button], PjxSlot()] = []
```

```html
<!-- button_group.pjx -->
<div id="{{ id }}" class="button-group">
    {% for button in buttons %}
        {{ button }}
    {% endfor %}
</div>
```

```python
group = ButtonGroup(
    id="actions",
    buttons=[
        Button(id="save", text="Save"),
        Button(id="cancel", text="Cancel"),
        Button(id="delete", text="Delete"),
    ],
)
```

Each list element still only exposes its rendered HTML via `{{ button }}` — see
[Nested components are opaque](#nested-components-are-opaque) above.

## Dictionaries of Components

The same `Slot`-collection annotation works for a `dict`, for named component collections:

```python
from typing import Annotated

from pyjinhx import BaseComponent
from pyjinhx._component import PjxSlot


class Widget(BaseComponent):
    id: str
    content: str


class Dashboard(BaseComponent):
    id: str
    widgets: Annotated[dict[str, str | Widget], PjxSlot()] = {}
```

```html
<!-- dashboard.pjx -->
<div id="{{ id }}" class="dashboard">
    <aside>{{ widgets.sidebar }}</aside>
    <main>{{ widgets.main }}</main>
    <footer>{{ widgets.footer }}</footer>
</div>
```

```python
dashboard = Dashboard(
    id="main",
    widgets={
        "sidebar": Widget(id="nav", content="Navigation"),
        "main": Widget(id="content", content="Main content"),
        "footer": Widget(id="foot", content="Footer"),
    },
)
```

## Deep Nesting

Components can be nested to any depth. Reusing the `Button` and `Card` classes from above:

```python
class Page(BaseComponent):
    id: str
    title: str
    main_card: Slot = ""
```

```python
page = Page(
    id="home",
    title="Welcome",
    main_card=Card(
        id="hero", title="Get Started", action=Button(id="cta", text="Sign Up")
    ),
)

html = page.render()
```

The rendering happens recursively - nested components are rendered before their parents.
