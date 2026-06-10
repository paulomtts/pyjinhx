import re

import pytest
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from pyjinhx import BaseComponent, Renderer


class CoercionProbe(BaseComponent):
    count: int = 0
    enabled: bool = False


PROBE_TEMPLATE = '<span id="{{ id }}">{{ count }}|{{ enabled }}</span>'


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
    assert re.search(r'id="px-\d+"', html)


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
