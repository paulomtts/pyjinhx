import importlib.util
import os
import sys
import tempfile

from pyjinhx.renderer import Renderer


def test_tag_template_auto_lookup_supports_jinja_extension():
    original_environment = Renderer.peek_default_environment()

    with tempfile.TemporaryDirectory() as temp_dir:
        child_template_path = os.path.join(temp_dir, "child.jinja")
        with open(child_template_path, "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        Renderer.set_default_environment(temp_dir)

        renderer = Renderer.get_default_renderer()
        rendered = renderer.render('<Child id="child-1" text="Hello"/>')
        assert rendered == '<span id="child-1">Hello</span>'

    Renderer.set_default_environment(original_environment)


def test_class_template_auto_lookup_supports_jinja_extension():
    original_environment = Renderer.peek_default_environment()

    with tempfile.TemporaryDirectory() as temp_dir:
        component_dir = os.path.join(temp_dir, "components")
        os.makedirs(component_dir, exist_ok=True)

        module_path = os.path.join(component_dir, "jinja_component.py")
        with open(module_path, "w") as file:
            file.write(
                "from pyjinhx import BaseComponent\n\n"
                "class JinjaAutoLookupComponent(BaseComponent):\n"
                "    id: str\n"
                "    text: str\n"
            )

        template_path = os.path.join(component_dir, "jinja_auto_lookup_component.jinja")
        with open(template_path, "w") as file:
            file.write('<div id="{{ id }}">{{ text }}</div>\n')

        Renderer.set_default_environment(temp_dir)

        spec = importlib.util.spec_from_file_location(
            "components.jinja_component", module_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["components.jinja_component"] = module
        spec.loader.exec_module(module)

        component_class = getattr(module, "JinjaAutoLookupComponent")
        component = component_class(id="cmp-1", text="Hello")
        rendered = str(component.render())
        assert rendered == '<div id="cmp-1">Hello</div>'

    Renderer.set_default_environment(original_environment)


def test_tag_template_lookup_supports_hyphen_separator():
    """Test that templates with hyphen separators (kebab-case) are found."""
    original_environment = Renderer.peek_default_environment()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create template with hyphen separator instead of underscore
        template_path = os.path.join(temp_dir, "button-group.html")
        with open(template_path, "w") as file:
            file.write('<div id="{{ id }}" class="btn-group">{{ content }}</div>\n')

        Renderer.set_default_environment(temp_dir)

        renderer = Renderer.get_default_renderer()
        rendered = renderer.render('<ButtonGroup id="bg-1">Buttons here</ButtonGroup>')
        assert rendered == '<div id="bg-1" class="btn-group">Buttons here</div>'

    Renderer.set_default_environment(original_environment)


def test_underscore_preferred_over_hyphen():
    """Test that underscore templates are preferred when both exist."""
    original_environment = Renderer.peek_default_environment()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create both underscore and hyphen versions
        with open(os.path.join(temp_dir, "nav_bar.html"), "w") as file:
            file.write('<nav id="{{ id }}">underscore</nav>\n')
        with open(os.path.join(temp_dir, "nav-bar.html"), "w") as file:
            file.write('<nav id="{{ id }}">hyphen</nav>\n')

        Renderer.set_default_environment(temp_dir)

        renderer = Renderer.get_default_renderer()
        rendered = renderer.render('<NavBar id="nav-1"/>')
        # underscore version should be preferred
        assert rendered == '<nav id="nav-1">underscore</nav>'

    Renderer.set_default_environment(original_environment)
