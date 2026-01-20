import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent, Renderer


def test_custom_html():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "container.html"), "w") as file:
            file.write("<div id={{ id }}>\n  {{ content }}\n</div>\n")
        with open(os.path.join(temp_dir, "message.html"), "w") as file:
            file.write("<span id={{ id }}>Hello {{ name }}!</span>\n")

        index_html = '<Container><Message name="Paulo"/></Container>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        expected_pattern = r"^<div id=container-[a-f0-9]{32}>\n  <span id=message-[a-f0-9]{32}>Hello Paulo!</span>\n</div>$"
        assert re.match(expected_pattern, rendered), (
            f"Output does not match expected pattern. Got: {rendered!r}"
        )


def test_deep_nesting():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "outer.html"), "w") as file:
            file.write(
                "<section id={{ id }} class={{ class }}>\n  {{ content }}\n</section>\n"
            )
        with open(os.path.join(temp_dir, "middle.html"), "w") as file:
            file.write("<div id={{ id }}>\n  {{ content }}\n</div>\n")
        with open(os.path.join(temp_dir, "inner.html"), "w") as file:
            file.write("<p id={{ id }}>{{ text }}</p>\n")

        index_html = '<Outer class="wrapper"><Middle><Inner text="Deep nesting works!"/></Middle></Outer>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r"^<section id=outer-[a-f0-9]{32} class=wrapper>\n  <div id=middle-[a-f0-9]{32}>\n  <p id=inner-[a-f0-9]{32}>Deep nesting works!</p>\n</div>\n</section>$",
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_multiple_children():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "list.html"), "w") as file:
            file.write("<ul id={{ id }}>\n  {{ content }}\n</ul>\n")
        with open(os.path.join(temp_dir, "item.html"), "w") as file:
            file.write("<li id={{ id }}>{{ text }}</li>\n")

        index_html = (
            '<List><Item text="First"/><Item text="Second"/><Item text="Third"/></List>'
        )
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r"^<ul id=list-[a-f0-9]{32}>\n  <li id=item-[a-f0-9]{32}>First</li><li id=item-[a-f0-9]{32}>Second</li><li id=item-[a-f0-9]{32}>Third</li>\n</ul>$",
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_mixed_content_and_components():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "panel.html"), "w") as file:
            file.write("<div id={{ id }} class={{ class }}>\n  {{ content }}\n</div>\n")
        with open(os.path.join(temp_dir, "action_button.html"), "w") as file:
            file.write("<button id={{ id }}>{{ label }}</button>\n")

        index_html = (
            '<Panel class="card">Before <ActionButton label="Click Me"/> After</Panel>'
        )
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r"^<div id=panel-[a-f0-9]{32} class=card>\n  Before <button id=actionbutton-[a-f0-9]{32}>Click Me</button> After\n</div>$",
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_manual_ids():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "header.html"), "w") as file:
            file.write(
                "<header id={{ id }}>\n  <h1>{{ title }}</h1>\n  {{ content }}\n</header>\n"
            )
        with open(os.path.join(temp_dir, "nav.html"), "w") as file:
            file.write("<nav id={{ id }}>{{ content }}</nav>\n")

        index_html = '<Header id="main-header" title="My Site"><Nav id="main-nav">Home | About</Nav></Header>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert (
            rendered
            == "<header id=main-header>\n  <h1>My Site</h1>\n  <nav id=main-nav>Home | About</nav>\n</header>"
        )


def test_complex_attributes():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "input.html"), "w") as file:
            file.write(
                "<input id={{ id }} type={{ type }} name={{ name }} placeholder={{ placeholder }} required={{ required }}/>\n"
            )

        index_html = '<Input type="text" name="username" placeholder="Enter username" required="true"/>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r"^<input id=input-[a-f0-9]{32} type=text name=username placeholder=Enter username required=true/>$",
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_empty_component():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "spacer.html"), "w") as file:
            file.write("<div id={{ id }} class={{ class }}>{{ content }}</div>\n")

        index_html = '<Spacer class="spacer"/>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r"^<div id=spacer-[a-f0-9]{32} class=spacer></div>$", rendered
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_auto_id_false_requires_manual_id():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "component.html"), "w") as file:
            file.write("<div id={{ id }}>{{ content }}</div>\n")

        index_html = "<Component/>"
        renderer = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=False,
        )

        try:
            renderer.render(index_html)
            assert False, "Should have raised ValueError for missing id"
        except ValueError as e:
            assert 'Missing required "id"' in str(e)


def test_auto_id_false_with_manual_id():
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "box.html"), "w") as file:
            file.write("<div id={{ id }} class={{ class }}>{{ content }}</div>\n")

        index_html = '<Box id="custom-box" class="container"/>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=False,
        ).render(index_html)

        assert rendered == "<div id=custom-box class=container></div>"


def test_renderer_uses_registered_class():
    """Test that Renderer uses registered BaseComponent classes when available."""

    class Button(BaseComponent):
        id: str
        text: str
        variant: str = "default"

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "button.html"), "w") as file:
            file.write(
                '<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>\n'
            )

        index_html = '<Button text="Click me" variant="primary"/>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r'^<button id="button-[a-f0-9]{32}" class="btn btn-primary">Click me</button>$',
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_renderer_fallback_to_generic_when_class_not_found():
    """Test that Renderer falls back to generic BaseComponent when class not registered."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "custom.html"), "w") as file:
            file.write('<div id="{{ id }}" class="{{ class }}">{{ content }}</div>\n')

        index_html = '<Custom class="test">Some content</Custom>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r'^<div id="custom-[a-f0-9]{32}" class="test">Some content</div>$', rendered
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_renderer_with_registered_class_and_nested_components():
    """Test that registered classes work with nested components."""

    class Card(BaseComponent):
        id: str
        title: str
        content: str = ""

    class Button(BaseComponent):
        id: str
        text: str

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "card.html"), "w") as file:
            file.write(
                '<div id="{{ id }}" class="card">\n  <h2>{{ title }}</h2>\n  {{ content }}\n</div>\n'
            )
        with open(os.path.join(temp_dir, "button.html"), "w") as file:
            file.write('<button id="{{ id }}">{{ text }}</button>\n')

        index_html = '<Card title="My Card"><Button text="Action"/></Card>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r'^<div id="card-[a-f0-9]{32}" class="card">\n  <h2>My Card</h2>\n  <button id="button-[a-f0-9]{32}">Action</button>\n</div>$',
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_renderer_with_registered_class_validation():
    """Test that registered classes enforce their field types and defaults."""

    class Input(BaseComponent):
        id: str
        type: str = "text"
        name: str
        placeholder: str = ""

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "input.html"), "w") as file:
            file.write(
                '<input id="{{ id }}" type="{{ type }}" name="{{ name }}" placeholder="{{ placeholder }}"/>\n'
            )

        index_html = '<Input name="username" placeholder="Enter username"/>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r'^<input id="input-[a-f0-9]{32}" type="text" name="username" placeholder="Enter username"/>$',
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"


def test_renderer_mixed_registered_and_generic():
    """Test mixing registered classes with generic components."""

    class Header(BaseComponent):
        id: str
        title: str

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "header.html"), "w") as file:
            file.write('<header id="{{ id }}"><h1>{{ title }}</h1></header>\n')
        with open(os.path.join(temp_dir, "footer.html"), "w") as file:
            file.write('<footer id="{{ id }}">{{ content }}</footer>\n')

        index_html = '<Header title="My Site"/><Footer>Copyright 2024</Footer>'
        rendered = Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)

        assert re.match(
            r'^<header id="header-[a-f0-9]{32}"><h1>My Site</h1></header><footer id="footer-[a-f0-9]{32}">Copyright 2024</footer>$',
            rendered,
        ), f"Output does not match expected pattern. Got: {rendered!r}"
