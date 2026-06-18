import pytest
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
    assert WidgetFac(id="i", title="x", count="7").count == 7  # coerced
    with pytest.raises(ValidationError):
        WidgetFac(id="i")  # missing required title


def test_factory_defaults_apply(env):
    WidgetFac = component("WidgetFac")
    assert WidgetFac(id="i", title="x").count == 0


def test_factory_no_header_is_permissive(env):
    BareFac = component("BareFac")
    inst = BareFac(id="i", foo="bar")  # extra='allow' keeps undeclared props
    assert "bar" in str(inst.render())
