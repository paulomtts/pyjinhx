# Nesting

PyJinHx makes it easy to compose components together. You can nest single components, lists of components, or dictionaries of components.

!!! note "Two nesting styles, two `id` rules"
    There are two ways to nest:

    - **Python field values** (this page) — you build child instances yourself; give each child an **explicit `id`** (auto-generated `pjx-<n>` ids are not stable hooks).
    - **PascalCase `<Tag/>` in templates** (see [PascalCase Tags](tags.md)) — the renderer instantiates children for you and can **auto-generate the `id`** when `auto_id=True` (the default).

!!! info "Component-typed fields are nesting points already"
    A field annotated with a component type — `Button`, `list[Button]`,
    `dict[str, Button]` — renders that value's HTML in place with no extra marker.
    `Slot` is the escape hatch for the ambiguous cases: a field that may hold *either*
    literal markup or a component, or a plain `str` that must be emitted unescaped (see
    [Escaping and slots](components.md#escaping-and-slots)). `Children` is the same idea
    for the field that receives a PascalCase tag's nested markup.

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

A list of nested components is just a `list[...]` of the child type — the same shape the
[todo example](https://github.com/paulomtts/pyjinhx/tree/master/examples/todo) uses for its rows:

```python
from pyjinhx import BaseComponent


class ButtonGroup(BaseComponent):
    id: str
    buttons: list[Button] = []
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

A `dict` works the same way, for named component collections:

```python
from pyjinhx import BaseComponent


class Widget(BaseComponent):
    id: str
    content: str


class Dashboard(BaseComponent):
    id: str
    widgets: dict[str, Widget] = {}
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
