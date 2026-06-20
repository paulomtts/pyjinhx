from typing import Any

import pytest

from pyjinhx import BaseComponent, Renderer
from pyjinhx.base import collect_extra_attrs
from pyjinhx.builtins import PJXPopoverTrigger


def test_collect_merges_extra_attrs_field_and_stray_attrs():
    inline_attrs: dict[str, Any] = {"data-stray": "2", "title": "hi"}
    component = PJXPopoverTrigger(
        id="t",
        content="go",
        extra_attrs={"data-explicit": "1"},
        **inline_attrs,
    )
    result = collect_extra_attrs(component)
    assert result == {"data-explicit": "1", "data-stray": "2", "title": "hi"}


def test_collect_skips_children_field_and_non_string_extras():
    component = PJXPopoverTrigger(id="t", content="go")
    result = collect_extra_attrs(component)
    # the children field ("content") must not leak into attrs
    assert "content" not in result
    assert result == {}


def _write(tmp_path, name, template):
    path = tmp_path / name
    path.write_text(template)
    return path


def test_app_component_passes_inline_attrs_to_root(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    _write(tmp_path, "app_btn.html", '<button class="x">{{ label }}</button>')

    class AppBtn(BaseComponent):
        label: str = ""

    renderer = Renderer.get_default_renderer()
    rendered = renderer.render('<AppBtn label="Hi" hx-post="/foo" hx-target="#bar"/>')

    assert 'hx-post="/foo"' in rendered
    assert 'hx-target="#bar"' in rendered


def test_app_component_inline_class_overrides_template_class(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    _write(tmp_path, "app_box.html", '<div class="base">{{ body }}</div>')

    class AppBox(BaseComponent):
        body: str = ""

    renderer = Renderer.get_default_renderer()
    rendered = renderer.render('<AppBox body="x" class="mt-4"/>')

    assert 'class="mt-4"' in rendered
    assert 'class="base"' not in rendered


def test_multi_root_template_raises(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    _write(tmp_path, "two_roots.html", "<div>a</div><div>b</div>")

    class TwoRoots(BaseComponent):
        pass

    renderer = Renderer.get_default_renderer()
    with pytest.raises(ValueError, match="exactly one root"):
        renderer.render("<TwoRoots/>")
