"""PJXTooltipTrigger renders the focusable element that reveals its tooltip tip (port of v0.x pyjinhx/builtins/ui/pjx_tooltip_trigger/pjx_tooltip_trigger.py)."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_tooltip_trigger import PJXTooltipTrigger
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def trigger_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXTooltipTrigger(id="tr", **kw), session)


def test_default_render_is_a_single_focusable_span(trigger_session):
    assert _html(trigger_session) == (
        '<span id="tr" class="pjx-tooltip__trigger" tabindex="0"></span>'
    )


def test_root_is_a_single_span(trigger_session):
    html = _html(trigger_session, content="Hover me")
    assert html.count("<span") == 1
    assert html.count("</span>") == 1


def test_trigger_is_keyboard_reachable(trigger_session):
    """focusin/focusout delegation only fires for a focusable trigger, hence tabindex."""
    assert 'tabindex="0"' in _html(trigger_session)


def test_custom_id_is_rendered(trigger_session):
    assert 'id="my-trigger"' in render(
        PJXTooltipTrigger(id="my-trigger"), trigger_session
    )


def test_class_name_appended_to_trigger(trigger_session):
    assert 'class="pjx-tooltip__trigger extra"' in _html(
        trigger_session, class_name="extra"
    )


def test_string_content_is_interpolated(trigger_session):
    assert ">Hover me</span>" in _html(trigger_session, content="Hover me")


def test_dropped_extra_attrs_field_is_rejected():
    """v0.x had no extra_attrs here either; extra="forbid" turns it into an error (ADR 0006)."""
    with pytest.raises(ValidationError):
        PJXTooltipTrigger(id="tr", extra_attrs={"data-x": "1"})  # type: ignore[call-arg]


def test_focus_visible_css_is_discovered_from_the_component_directory():
    """The :focus-visible outline rule lives here, not on the root."""
    descriptor = PJXTooltipTrigger.__pjx_descriptor__
    assert any(p.name == "pjx_tooltip_trigger.css" for p in descriptor.css_paths)
