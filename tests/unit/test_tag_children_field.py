"""Tag children map into each component's children field (PJXTooltip uses ``content``)."""

import pytest
from jinja2 import Environment, FileSystemLoader
from typing import Annotated

from pyjinhx import BaseComponent, Children, Renderer, Slot
from pyjinhx.base import PjxSlot
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


# ---------------------------------------------------------------------------
# Task 3: Route children via _pjx_children_target
# ---------------------------------------------------------------------------


def test_sole_slot_children_land_in_inferred_field(tmp_path):
    class SearchFieldTag(BaseComponent):
        filters: Annotated[str | BaseComponent | None, PjxSlot()] = None

    (tmp_path / "search_field_tag.html").write_text(
        '<div id="{{ id }}"><span class="filters">{{ filters }}</span></div>'
    )
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    rendered = renderer.render('<SearchFieldTag id="sf"><i>x</i></SearchFieldTag>')

    assert '<span class="filters"><i>x</i></span>' in rendered


def test_children_alias_field_receives_children(tmp_path):
    class PanelTag(BaseComponent):
        head: Slot = ""
        body: Children = ""

    (tmp_path / "panel_tag.html").write_text(
        '<div>{{ head }}|<section>{{ body }}</section></div>'
    )
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    rendered = renderer.render('<PanelTag id="p"><b>kid</b></PanelTag>')

    assert '<section><b>kid</b></section>' in rendered


def test_ambiguous_component_with_children_raises_clear_error(tmp_path):
    class MenuTag(BaseComponent):
        trigger: Slot = ""
        items: Annotated[str | BaseComponent, PjxSlot()] = ""

    (tmp_path / "menu_tag.html").write_text('<div>{{ trigger }}{{ items }}</div>')
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    with pytest.raises(ValueError) as exc:
        renderer.render('<MenuTag id="m"><b>kid</b></MenuTag>')
    msg = str(exc.value)
    assert "MenuTag" in msg
    assert "trigger" in msg and "items" in msg
    assert "children=True" in msg


def test_ambiguous_existing_instance_with_children_raises_clear_error(tmp_path):
    """The existing-instance re-render branch (tags.py:334) must also raise for
    an ambiguous (None-target) component when children are nested."""

    class Menu3Tag(BaseComponent):
        trigger: Slot = ""
        items: Annotated[str | BaseComponent, PjxSlot()] = ""

    (tmp_path / "menu3_tag.html").write_text('<div>{{ trigger }}{{ items }}</div>')
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    Menu3Tag(id="reg1")  # pre-register an instance so the existing-instance path fires
    with pytest.raises(ValueError) as exc:
        renderer.render('<Menu3Tag id="reg1"><b>kid</b></Menu3Tag>')
    assert "Menu3Tag" in str(exc.value)


def test_ambiguous_component_props_only_does_not_crash(tmp_path):
    """Regression: props-only construction of an ambiguous (None-target)
    component must not run init_kwargs[None] = "" (TypeError: keywords must be
    strings). This guard stays green before AND after the reader switch — its
    value is catching a regression once tags.py reads the None-valued target."""

    class Menu2Tag(BaseComponent):
        trigger: Slot = ""
        items: Annotated[str | BaseComponent, PjxSlot()] = ""

    (tmp_path / "menu2_tag.html").write_text('<div>{{ trigger }}{{ items }}</div>')
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    rendered = renderer.render('<Menu2Tag id="m2" trigger="go"/>')

    assert "go" in rendered


def test_subclass_of_override_component_routes_children_to_inherited_field(tmp_path):
    class BoxedTag(BaseComponent):
        _pjx_children_field = "kids"
        kids: str = ""

    class SubBoxedTag(BoxedTag):
        extra: str = ""

    (tmp_path / "sub_boxed_tag.html").write_text('<div id="{{ id }}">{{ kids }}</div>')
    renderer = Renderer(Environment(loader=FileSystemLoader(str(tmp_path))))

    rendered = renderer.render('<SubBoxedTag id="sb">inherited</SubBoxedTag>')

    assert '<div id="sb">inherited</div>' in rendered
