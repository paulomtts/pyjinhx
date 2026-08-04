"""PJXTooltipContent renders the hidden tip element a tooltip trigger reveals (port of v0.x pyjinhx/builtins/ui/pjx_tooltip_content/pjx_tooltip_content.py)."""

import dataclasses

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_tooltip_content import PJXTooltipContent
from pyjinhx._component import BaseComponent, Slot
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def content_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXTooltipContent(id="tc", **kw), session)


def test_default_render_is_a_single_hidden_tip(content_session):
    assert _html(content_session) == (
        '<span id="tc" class="pjx-tooltip__tip" role="tooltip" hidden></span>'
    )


def test_root_is_a_single_span(content_session):
    html = _html(content_session, content="Tip")
    assert html.count("<span") == 1
    assert html.count("</span>") == 1


def test_class_name_appended_to_tip(content_session):
    assert 'class="pjx-tooltip__tip extra"' in _html(
        content_session, class_name="extra"
    )


def test_string_content_is_interpolated(content_session):
    assert ">Tip text</span>" in _html(content_session, content="Tip text")


def test_empty_content_renders_an_empty_tip(content_session):
    assert _html(content_session).endswith("></span>")


class TipChild(BaseComponent):
    """A minimal component child, to prove a nested component renders inside the tip."""

    content: Slot = ""


@pytest.fixture
def tip_child_template(tmp_path):
    """Give TipChild a real template on disk and repoint its descriptor at it."""
    path = tmp_path / "tip_child.pjx"
    path.write_text('<em id="{{ id }}" class="child">{{ content }}</em>')
    TipChild.__pjx_descriptor__ = dataclasses.replace(
        TipChild.__pjx_descriptor__, template_path=path
    )
    yield path


def test_component_content_renders_inside_the_tip(content_session, tip_child_template):
    html = _html(content_session, content=TipChild(id="c", content="Inner"))
    assert '<em id="c" class="child">Inner</em>' in html


def test_dropped_extra_attrs_field_is_rejected():
    """v0.x had no extra_attrs here either; extra="forbid" turns it into an error (ADR 0006)."""
    with pytest.raises(ValidationError):
        PJXTooltipContent(id="tc", extra_attrs={"data-x": "1"})  # type: ignore[call-arg]


def test_positioning_css_is_discovered_from_the_component_directory():
    """The fixed/visible-transition rules pjx_tooltip.js toggles live here, not on the root."""
    descriptor = PJXTooltipContent.__pjx_descriptor__
    assert any(p.name == "pjx_tooltip_content.css" for p in descriptor.css_paths)
