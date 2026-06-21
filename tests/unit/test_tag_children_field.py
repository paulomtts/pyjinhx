"""Tag children map into each component's children field (PJXTooltip uses ``content``)."""

import pytest
from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent, Renderer
from pyjinhx.builtins import PJXModal, PJXTooltip, PJXTooltipContent, PJXTooltipTrigger  # noqa: F401  (importing registers the tags)


def test_tooltip_tag_children_map_to_content(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render(
        '<PJXTooltip id="t">'
        '<PJXTooltipTrigger id="t-tr">hover me</PJXTooltipTrigger>'
        '<PJXTooltipContent id="t-tc">helpful text</PJXTooltipContent>'
        '</PJXTooltip>'
    )

    assert '<span id="t-tc" class="pjx-tooltip__tip"' in rendered
    assert "helpful text</span>" in rendered
    assert '<span id="t-tr" class="pjx-tooltip__trigger"' in rendered
    assert ">hover me</span>" in rendered


def test_component_with_content_field_still_maps_children_to_content(tmp_path):
    class ContentBox(BaseComponent):
        content: str = ""

    (tmp_path / "content_box.html").write_text('<div id="{{ id }}">{{ content }}</div>')
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    rendered = renderer.render('<ContentBox id="cb">hello</ContentBox>')

    assert '<div id="cb">hello</div>' in rendered


def test_preregistered_tooltip_instance_update_maps_children_to_content(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    PJXTooltip(id="t2")
    rendered = renderer.render(
        '<PJXTooltip id="t2">'
        '<PJXTooltipContent id="t2-tc">updated tip</PJXTooltipContent>'
        '</PJXTooltip>'
    )

    assert '<span id="t2-tc" class="pjx-tooltip__tip"' in rendered
    assert "updated tip</span>" in rendered


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


def test_tooltip_both_children_and_content_attr_raises(tmp_path):
    """<PJXTooltip content="explicit">inner</PJXTooltip> must raise ValueError."""
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    with pytest.raises(ValueError, match="both children and the 'content' attribute"):
        renderer.render('<PJXTooltip id="tt" content="explicit">inner</PJXTooltip>')


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
