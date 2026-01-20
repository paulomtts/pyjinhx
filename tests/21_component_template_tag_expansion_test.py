import os
import tempfile

from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent
from pyjinhx.renderer import Renderer


def test_component_template_can_expand_custom_tags():
    """Test that PascalCase tags inside component templates are expanded."""

    class Child(BaseComponent):
        id: str
        text: str

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create child template
        with open(os.path.join(temp_dir, "child.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        # Create parent template with embedded Child tag
        with open(os.path.join(temp_dir, "parent.html"), "w") as file:
            file.write(
                '<div id="{{ id }}"><Child id="child-1" text="{{ child_text }}"/></div>\n'
            )

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        # Render using Renderer.render() with PascalCase tags
        rendered = renderer.render('<Parent id="parent-1" child_text="Hello"/>')

        assert rendered == '<div id="parent-1"><span id="child-1">Hello</span></div>'


def test_nested_custom_tags_in_renderer():
    """Test deeply nested PascalCase tags are all expanded."""

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "outer.html"), "w") as file:
            file.write('<section id="{{ id }}">{{ content }}</section>\n')

        with open(os.path.join(temp_dir, "inner.html"), "w") as file:
            file.write('<p id="{{ id }}">{{ text }}</p>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<Outer id="outer-1"><Inner id="inner-1" text="Nested content"/></Outer>'
        )

        assert rendered == '<section id="outer-1"><p id="inner-1">Nested content</p></section>'
