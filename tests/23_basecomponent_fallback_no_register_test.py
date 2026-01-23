import os
import tempfile

from jinja2 import Environment, FileSystemLoader

from pyjinhx import Registry
from pyjinhx.renderer import Renderer


def test_fallback_basecomponent_not_registered():
    """Test that PascalCase tags without registered classes don't pollute the registry."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a FallbackPanel template (no registered FallbackPanel class)
        # Note: template filename uses snake_case
        with open(os.path.join(temp_dir, "fallback_panel.html"), "w") as file:
            file.write('<div id="{{ id }}" class="panel">{{ content }}</div>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        # First render
        rendered1 = renderer.render('<FallbackPanel id="reserved-panel">Content 1</FallbackPanel>')
        assert '<div id="reserved-panel" class="panel">Content 1</div>' == rendered1

        # The fallback BaseComponent should NOT be in the registry
        key = Registry.make_key("BaseComponent", "reserved-panel")
        assert key not in Registry.get_instances()


def test_repeated_renders_with_same_id_no_error():
    """Test that rendering the same PascalCase tag twice does not raise TypeError."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Note: template filename uses snake_case
        with open(os.path.join(temp_dir, "generic_box.html"), "w") as file:
            file.write('<div id="{{ id }}" class="box">{{ content }}</div>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        # First render
        rendered1 = renderer.render('<GenericBox id="reserved-box">First</GenericBox>')
        assert '<div id="reserved-box" class="box">First</div>' == rendered1

        # Second render - this used to raise TypeError before the fix
        rendered2 = renderer.render('<GenericBox id="reserved-box">Second</GenericBox>')
        assert '<div id="reserved-box" class="box">Second</div>' == rendered2


def test_registered_class_still_works():
    """Test that registered component classes still work correctly."""
    from pyjinhx import BaseComponent

    Registry.clear_instances()

    class Widget(BaseComponent):
        id: str
        label: str = ""

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "widget.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ label }}</span>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        # Render with registered class
        rendered = renderer.render('<Widget id="my-widget" label="Hello"/>')
        assert '<span id="my-widget">Hello</span>' == rendered

        # The Widget instance SHOULD be in the registry (it's a proper class, not fallback)
        key = Registry.make_key("Widget", "my-widget")
        assert key in Registry.get_instances()
        assert type(Registry.get_instances()[key]).__name__ == "Widget"
