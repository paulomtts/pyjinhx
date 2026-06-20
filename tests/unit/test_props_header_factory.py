import pytest
from jinja2 import DictLoader, Environment

from pyjinhx import Renderer
from pyjinhx.base import BaseComponent, component


@pytest.fixture()
def env(tmp_path):
    (tmp_path / "bare_fac.html").write_text("<div>{{ foo }}</div>", encoding="utf-8")
    Renderer.set_default_environment(str(tmp_path))


def test_factory_no_header_is_permissive(env):
    BareFac = component("BareFac")
    inst = BareFac(id="i", foo="bar")  # extra='allow' keeps undeclared props
    assert "bar" in str(inst.render())


def test_factory_dictloader_env_does_not_raise():
    """Regression: component() must not raise when the default env uses a
    non-FileSystemLoader (e.g. DictLoader).  component() now returns a bare
    placeholder immediately without touching the renderer, so this test confirms
    no exception is raised.
    """
    Renderer.set_default_environment(Environment(loader=DictLoader({})))
    try:
        result = component("SomeUnresolvable")
        assert issubclass(result, BaseComponent)
    finally:
        # Restore a clean state so other tests are not affected.
        Renderer.set_default_environment(None)
