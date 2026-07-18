import re

import pytest
from jinja2 import Environment, FileSystemLoader
from pydantic import Field, ValidationError

from pyjinhx import BaseComponent, Renderer


class CoercionProbe(BaseComponent):
    count: int = 0
    enabled: bool = False


PROBE_TEMPLATE = '<span id="{{ id }}">{{ count }}|{{ enabled }}</span>'


class StructuralProbe(BaseComponent):
    sources: list = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    label: str | list = ""


STRUCTURAL_PROBE_TEMPLATE = '<span id="{{ id }}">{{ sources }}|{{ meta }}|{{ label }}</span>'


def test_json_string_attr_coerces_to_list(tmp_path):
    (tmp_path / "structural_probe.html").write_text(STRUCTURAL_PROBE_TEMPLATE)
    env = Environment(loader=FileSystemLoader(str(tmp_path)))
    renderer = Renderer(env)
    html = renderer.render(
        '<StructuralProbe id="s1" sources=\'[{"id": "a"}]\'/>'
    )
    assert "[{&#39;id&#39;: &#39;a&#39;}]" in html or "[{'id': 'a'}]" in html


def test_json_string_attr_coerces_to_dict(tmp_path):
    (tmp_path / "structural_probe.html").write_text(STRUCTURAL_PROBE_TEMPLATE)
    env = Environment(loader=FileSystemLoader(str(tmp_path)))
    renderer = Renderer(env)
    html = renderer.render('<StructuralProbe id="s2" meta=\'{"k": "v"}\'/>')
    assert "'k': 'v'" in html


def test_invalid_json_raises_clear_error():
    with pytest.raises(ValidationError):
        StructuralProbe(sources="[not json")


def test_union_with_str_is_not_coerced():
    probe = StructuralProbe(label="[1, 2, 3]")
    assert probe.label == "[1, 2, 3]"


def test_non_json_looking_string_left_alone():
    with pytest.raises(ValidationError):
        StructuralProbe(sources="plain text")


def test_tag_attrs_coerce_to_int_and_bool(tmp_path):
    (tmp_path / "coercion_probe.html").write_text(PROBE_TEMPLATE)
    env = Environment(loader=FileSystemLoader(str(tmp_path)))
    renderer = Renderer(env)
    html = renderer.render('<CoercionProbe id="p1" count="32" enabled="true"/>')
    assert ">32|True<" in html


def test_tag_without_id_uses_px_format(tmp_path):
    (tmp_path / "coercion_probe.html").write_text(PROBE_TEMPLATE)
    env = Environment(loader=FileSystemLoader(str(tmp_path)))
    renderer = Renderer(env)
    html = renderer.render('<CoercionProbe count="1"/>')
    assert re.search(r'id="pjx-\d+"', html)


def test_instance_reuse_update_is_validated(tmp_path):
    (tmp_path / "coercion_probe.html").write_text(PROBE_TEMPLATE)
    env = Environment(loader=FileSystemLoader(str(tmp_path)))
    renderer = Renderer(env)
    CoercionProbe(id="reuse-1", count=1)
    html = renderer.render('<CoercionProbe id="reuse-1" count="7"/>')
    assert ">7|" in html


def test_instance_reuse_invalid_update_raises(tmp_path):
    (tmp_path / "coercion_probe.html").write_text(PROBE_TEMPLATE)
    env = Environment(loader=FileSystemLoader(str(tmp_path)))
    renderer = Renderer(env)
    CoercionProbe(id="reuse-2", count=1)
    with pytest.raises(ValidationError):
        renderer.render('<CoercionProbe id="reuse-2" count="not-a-number"/>')


def test_instance_reuse_preserves_nested_components(tmp_path):
    from pyjinhx.builtins import PJXBadge, PJXCardBody

    (tmp_path / "unused_probe.html").write_text("<i></i>")
    original_environment = Renderer.peek_default_environment()
    try:
        Renderer.set_default_environment(str(tmp_path))
        renderer = Renderer.get_default_renderer()
        PJXCardBody(id="cb1", content=PJXBadge(id="b1", label="hi"))
        html = renderer.render('<PJXCardBody id="cb1" class_name="updated"/>')
        assert "hi" in html          # PJXBadge subclass state survived the reuse update
        assert "pjx-badge" in html    # it rendered as a PJXBadge, not a degraded BaseComponent
        assert "updated" in html     # the update itself applied
    finally:
        Renderer.set_default_environment(original_environment)
