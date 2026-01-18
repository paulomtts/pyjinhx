import pytest
from jinja2 import DictLoader, Environment
from jinja2.exceptions import TemplateNotFound

from pyjinhx import BaseComponent
from pyjinhx.renderer import Renderer


def test_missing_template_file():
    class MissingTemplateComponent(BaseComponent):
        id: str
        text: str

    component = MissingTemplateComponent(id="missing-1", text="Test")

    with pytest.raises(TemplateNotFound):
        component.render()


def test_non_filesystem_loader_error():
    class TestComponent(BaseComponent):
        id: str
        text: str

    dict_loader = DictLoader({"template.html": "<div>{{ text }}</div>"})
    env = Environment(loader=dict_loader)
    original_environment = Renderer.peek_default_environment()
    Renderer.set_default_environment(env)

    component = TestComponent(id="test-1", text="Test")

    with pytest.raises(ValueError, match="Jinja2 loader must be a FileSystemLoader"):
        component.render()

    Renderer.set_default_environment(original_environment)

