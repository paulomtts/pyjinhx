import pytest
from jinja2 import DictLoader, Environment
from pydantic import ValidationError

from pyjinhx import Renderer
from pyjinhx.base import BaseComponent, component


@pytest.fixture()
def env(tmp_path):
    (tmp_path / "widget_fac.html").write_text(
        '{#def title: str, count: int = 0 #}\n<div>{{ title }}-{{ count }}</div>',
        encoding="utf-8",
    )
    (tmp_path / "bare_fac.html").write_text("<div>{{ foo }}</div>", encoding="utf-8")
    Renderer.set_default_environment(str(tmp_path))


def test_factory_builds_validated_fields(env):
    WidgetFac = component("WidgetFac")
    assert issubclass(WidgetFac, BaseComponent)
    assert WidgetFac(id="i", title="x", count="7").count == 7  # type: ignore[attr-defined]  # coerced; header-defined field
    with pytest.raises(ValidationError):
        WidgetFac(id="i")  # missing required title


def test_factory_defaults_apply(env):
    WidgetFac = component("WidgetFac")
    assert WidgetFac(id="i", title="x").count == 0  # type: ignore[attr-defined]  # header-defined field


def test_factory_no_header_is_permissive(env):
    BareFac = component("BareFac")
    inst = BareFac(id="i", foo="bar")  # extra='allow' keeps undeclared props
    assert "bar" in str(inst.render())


def test_factory_dictloader_env_does_not_raise():
    """Regression: component() must not raise when the default env uses a
    non-FileSystemLoader (e.g. DictLoader).  _find_template_for_tag() raises
    ValueError("Jinja2 loader must be a FileSystemLoader") for such loaders;
    the except clause in component() must catch it and fall back to a bare
    placeholder class instead of propagating the error.
    """
    Renderer.set_default_environment(Environment(loader=DictLoader({})))
    try:
        result = component("SomeUnresolvable")
        assert issubclass(result, BaseComponent)
    finally:
        # Restore a clean state so other tests are not affected.
        Renderer.set_default_environment(None)
