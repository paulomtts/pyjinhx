# Template Rendering

Besides instantiating components in Python, you can use HTML-like syntax with the `Renderer` class. This is useful for quick prototyping or when you want to compose pages in a more declarative way.

## Basic Usage

```python
from pyjinhx import Renderer

renderer = Renderer.get_default_renderer()
html = renderer.render('<Button text="Click me"/>')
```

!!! tip "Configuring the Renderer"
    See the [Configuration](configuration.md) page for details on setting up template paths and Jinja environments.

## PascalCase Tags

The renderer recognizes PascalCase tags as components:

```python
html = renderer.render("""
    <Header title="My Site"/>
    <Nav>Home | About | Contact</Nav>
    <Footer>Copyright 2024</Footer>
""")
```

Standard HTML tags (lowercase) are passed through unchanged:

```python
html = renderer.render("""
    <div class="container">
        <Button text="Click"/>
    </div>
""")
```

## Registered vs Generic Components

### Registered Components

If a `BaseComponent` subclass exists, its validation is applied:

```python
from pyjinhx import BaseComponent

class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"  # Has default
```

```python
# Uses Button class - variant defaults to "default"
html = renderer.render('<Button text="Click"/>')
```

### Generic Components

If no class is registered, a generic `BaseComponent` is used:

```python
# No Card class defined, but card.html exists
html = renderer.render('<Card title="Hello">Content</Card>')
```

The template receives all attributes as context variables.

## Nesting in Templates

Nest components using standard HTML-like syntax:

```python
html = renderer.render("""
    <Page title="Welcome">
        <Card title="Get Started">
            <Button text="Sign Up" variant="primary"/>
        </Card>
    </Page>
""")
```

## The `content` Variable

Child content is available as `{{ content }}` in templates:

```html
<!-- card.html -->
<div id="{{ id }}" class="card">
    <h2>{{ title }}</h2>
    <div class="body">
        {{ content }}
    </div>
</div>
```

```python
html = renderer.render("""
    <Card title="Note">
        This text becomes the content variable.
    </Card>
""")
```

## Attributes

Pass attributes as you would in HTML:

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

All attributes are available in the template context.

## Auto-Generated IDs

By default, `auto_id=True` generates UUIDs for components without explicit IDs:

```python
# ID is auto-generated
html = renderer.render('<Button text="Click"/>')
# Result: <button id="button-a1b2c3d4...">Click</button>
```

Provide explicit IDs when needed:

```python
html = renderer.render('<Button id="submit-btn" text="Submit"/>')
# Result: <button id="submit-btn">Submit</button>
```

### Disabling Auto-ID

```python
renderer = Renderer.get_default_renderer(auto_id=False)

# This will raise ValueError - id is required
html = renderer.render('<Button text="Click"/>')

# This works
html = renderer.render('<Button id="my-btn" text="Click"/>')
```
