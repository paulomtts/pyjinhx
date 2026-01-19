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
