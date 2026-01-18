import os
import tempfile

from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent
from pyjinhx.renderer import Renderer


def test_component_template_can_expand_custom_tags_when_enabled():
    original_environment = Renderer.peek_default_environment()

    class Child(BaseComponent):
        id: str
        text: str

    class Parent(BaseComponent):
        id: str
        child_text: str

    with tempfile.TemporaryDirectory() as temp_dir:
        child_template_path = os.path.join(temp_dir, "child.html")
        with open(child_template_path, "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        parent_template_path = os.path.join(temp_dir, "parent.html")
        with open(parent_template_path, "w") as file:
            file.write(
                '<div id="{{ id }}"><Child id="child-1" text="{{ child_text }}"/></div>\n'
            )

        Renderer.set_default_environment(Environment(loader=FileSystemLoader(temp_dir)))

        parent = Parent(id="parent-1", child_text="Hello", html=[parent_template_path])

        rendered = str(parent.render())
        assert rendered == '<div id="parent-1"><span id="child-1">Hello</span></div>'

    Renderer.set_default_environment(original_environment)
