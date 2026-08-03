"""PJXAccordionGroup renders the wrapper that scopes exclusive/multi behavior (port of v0.x pyjinhx/builtins/ui/pjx_accordion_group)."""

import dataclasses

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_accordion_group import PJXAccordionGroup
from pyjinhx.component import BaseComponent, Slot
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def group_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXAccordionGroup(id="g", **kw), session)


def test_default_render_matches_v0x_markup(group_session):
    assert _html(group_session) == (
        '<div id="g" class="pjx-accordion-group" data-pjx-accordion-group'
        ' data-mode="multi" style="--pjx-accordion-group-gap: 0"></div>'
    )


def test_exclusive_mode_reflected_in_data_mode(group_session):
    assert 'data-mode="exclusive"' in _html(group_session, mode="exclusive")


def test_default_open_none_omits_the_data_attribute(group_session):
    assert "data-default-open" not in _html(group_session)


def test_default_open_first_emits_the_data_attribute(group_session):
    assert 'data-default-open="first"' in _html(group_session, default_open="first")


def test_gap_lands_in_the_custom_property(group_session):
    assert "--pjx-accordion-group-gap: 1rem" in _html(group_session, gap="1rem")


def test_class_name_appended_to_root(group_session):
    assert 'class="pjx-accordion-group mine"' in _html(group_session, class_name="mine")


def test_empty_class_name_adds_nothing(group_session):
    assert 'class="pjx-accordion-group"' in _html(group_session, class_name="")


def test_mode_outside_the_literal_is_rejected():
    with pytest.raises(ValidationError):
        PJXAccordionGroup(id="g", mode="nope")  # pyright: ignore[reportArgumentType]


def test_default_open_outside_the_literal_is_rejected():
    with pytest.raises(ValidationError):
        PJXAccordionGroup(id="g", default_open="some")  # pyright: ignore[reportArgumentType]


class GroupChild(BaseComponent):
    """A minimal component child, to prove a nested component renders inside the group."""

    content: Slot = ""


@pytest.fixture
def group_child_template(tmp_path):
    """Give GroupChild a real template on disk and repoint its descriptor at it."""
    path = tmp_path / "group_child.pjx"
    path.write_text('<span id="{{ id }}" class="child">{{ content }}</span>')
    GroupChild.__pjx_descriptor__ = dataclasses.replace(
        GroupChild.__pjx_descriptor__, template_path=path
    )
    yield path


def test_component_content_renders_inside_root(group_session, group_child_template):
    html = _html(group_session, content=GroupChild(id="i", content="item"))
    assert html.count("<div") == 1
    assert '<span id="i" class="child">item</span>' in html


def test_assets_are_discovered_from_the_component_directory():
    """JS sits next to the module and is picked up by the descriptor, with no manual wiring."""
    descriptor = PJXAccordionGroup.__pjx_descriptor__
    assert descriptor.js_paths
    assert any(p.name == "pjx_accordion_group.js" for p in descriptor.js_paths)
