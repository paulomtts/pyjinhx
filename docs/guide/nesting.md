# Nesting

PyJinHx makes it easy to compose components together. You can nest single components, lists of components, or dictionaries of components.

## Direct Nesting

Pass a component as a field value:

```python
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str


class Card(BaseComponent):
    id: str
    title: str
    action: Button  # Nested component
```

```html
<!-- card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <div class="actions">
        {{ action }}
    </div>
</div>
```

```python
card = Card(
    id="hero",
    title="Welcome",
    action=Button(id="cta", text="Get Started")
)
html = card.render()
```

## Accessing Nested Component Properties

Nested components are wrapped in `NestedComponentWrapper`, giving you access to both the rendered HTML and the original props:

```html
<!-- card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>

    <!-- Render the component -->
    {{ action }}

    <!-- Access component properties -->
    <p>Button text: {{ action.props.text }}</p>
    <p>Button ID: {{ action.props.id }}</p>
</div>
```

## Lists of Components

Use a list to render multiple components:

```python
class ButtonGroup(BaseComponent):
    id: str
    buttons: list[Button]
```

```html
<!-- button_group.html -->
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
    ]
)
```

### Accessing List Item Properties

```html
<div id="{{ id }}" class="button-group">
    {% for button in buttons %}
        <div class="button-wrapper" data-text="{{ button.props.text }}">
            {{ button }}
        </div>
    {% endfor %}
</div>
```

### Mixed Collections

Combine different types in lists and dicts:

```python
class Container(BaseComponent):
    id: str
    items: list[Button | Card | Widget]
```

```html
{% for item in items %}
    <div class="item">{{ item }}</div>
{% endfor %}
```

## Dictionaries of Components

Use dictionaries for named component collections:

```python
class Dashboard(BaseComponent):
    id: str
    widgets: dict[str, Widget]
```

```html
<!-- dashboard.html -->
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
    }
)
```

## Wrappers

The inner content of a tag becomes `{{ content }}` in the component template:

```python
html = renderer.render("""
    <Card title="Note">
        This text becomes the content variable.
    </Card>
""")
```

## Deep Nesting

Components can be nested to any depth:

```python
class Button(BaseComponent):
    id: str
    text: str


class Card(BaseComponent):
    id: str
    title: str
    action: Button


class Page(BaseComponent):
    id: str
    title: str
    main_card: Card
```

```python
page = Page(
    id="home",
    title="Welcome",
    main_card=Card(
        id="hero",
        title="Get Started",
        action=Button(id="cta", text="Sign Up")
    )
)

html = page.render()
```

The rendering happens recursively - nested components are rendered before their parents.