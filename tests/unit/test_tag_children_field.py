"""Tag children map into each component's children field (PJXTooltip uses ``tip``)."""

import pytest
from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent, Renderer
from pyjinhx.builtins import PJXModal, PJXTooltip  # noqa: F401  (importing registers the tags)


def test_tooltip_tag_children_map_to_tip(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render(
        '<PJXTooltip id="t" trigger="hover me">helpful text</PJXTooltip>'
    )

    assert (
        '<span class="pjx-tooltip__tip" id="t-tip" role="tooltip" hidden>'
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

    PJXTooltip(id="t2", trigger="hover me")
    rendered = renderer.render('<PJXTooltip id="t2">updated tip</PJXTooltip>')

    assert (
        '<span class="pjx-tooltip__tip" id="t2-tip" role="tooltip" hidden>'
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
    """<PJXTooltip tip="explicit">inner</PJXTooltip> must raise ValueError."""
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    with pytest.raises(ValueError, match="both children and the 'tip' attribute"):
        renderer.render('<PJXTooltip id="tt" tip="explicit">inner tip</PJXTooltip>')


def test_modal_tag_children_map_to_content(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render('<PJXModal id="m">CHILD</PJXModal>')

    assert 'class="pjx-modal__box">CHILD</div>' in rendered


def test_modal_both_children_and_content_attr_raises(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    with pytest.raises(ValueError, match="both children and the 'content' attribute"):
        renderer.render('<PJXModal id="m2" content="x">y</PJXModal>')
