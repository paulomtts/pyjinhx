import os

from jinja2 import Environment, FileSystemLoader

from pyjinhx.renderer import Renderer


def test_set_default_environment():
    original_environment = Renderer.peek_default_environment()

    custom_root = os.path.join(os.getcwd(), "tests")
    custom_env = Environment(loader=FileSystemLoader(custom_root))
    Renderer.set_default_environment(custom_env)

    assert Renderer.get_default_environment() == custom_env
    assert Renderer.get_default_environment().loader.searchpath[0] == custom_root

    Renderer.set_default_environment(original_environment)

