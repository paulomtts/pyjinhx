"""Tag children map into each component's children field (Tooltip uses ``tip``)."""

import pytest
from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent, Renderer
from pyjinhx.builtins import Modal, Tooltip


def test_tooltip_tag_children_map_to_tip(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render(
        '<Tooltip id="t" trigger="hover me">helpful text</Tooltip>'
    )

    assert (
        '<span class="px-tooltip__tip" id="t-tip" role="tooltip" hidden>'
        "helpful text</span>" in rendered
    )
    assert ">hover me</span>" in rendered


def test_component_with_content_field_still_maps_children_to_content(tmp_path):
    class ContentBox(BaseComponent):
        content: str = ""

    (tmp_path / "content_box.html").write_text('<div id="{{ id }}">{{ content }}</div>')
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    rendered = renderer.render('<ContentBox id="cb">hello</ContentBox>')

    assert '<div id="cb">hello</div>' in rendered


def test_preregistered_tooltip_instance_update_maps_children_to_tip(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    Tooltip(id="t2", trigger="hover me")
    rendered = renderer.render('<Tooltip id="t2">updated tip</Tooltip>')

    assert (
        '<span class="px-tooltip__tip" id="t2-tip" role="tooltip" hidden>'
        "updated tip</span>" in rendered
    )
    assert ">hover me</span>" in rendered


# ---------------------------------------------------------------------------
# Error: both children and children-field attr supplied via tag
# ---------------------------------------------------------------------------


def test_both_children_and_content_attr_raises(tmp_path):
    """<ContentPane content="explicit">inner</ContentPane> must raise ValueError."""

    class ContentPane(BaseComponent):
        content: str = ""

    (tmp_path / "content_pane.html").write_text('<div>{{ content }}</div>')
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    with pytest.raises(ValueError, match="both children and the 'content' attribute"):
        renderer.render('<ContentPane id="cb" content="explicit">inner</ContentPane>')


def test_both_children_and_tip_attr_raises(tmp_path):
    """<Tooltip tip="explicit">inner</Tooltip> must raise ValueError."""
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    with pytest.raises(ValueError, match="both children and the 'tip' attribute"):
        renderer.render('<Tooltip id="tt" tip="explicit">inner tip</Tooltip>')


def test_modal_tag_children_map_to_body(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render('<Modal id="m">CHILD</Modal>')

    assert 'id="m-body">CHILD</div>' in rendered


def test_modal_both_children_and_body_attr_raises(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    with pytest.raises(ValueError, match="both children and the 'body' attribute"):
        renderer.render('<Modal id="m2" body="x">y</Modal>')
