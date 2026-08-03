"""PJXPopoverPanel renders the hidden-by-default floating panel a trigger reveals (port of v0.x pyjinhx/builtins/ui/pjx_popover/pjx_popover_panel.html)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_popover_panel import PJXPopoverPanel
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def panel_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXPopoverPanel(id="pl", **kw), session)


def test_default_render_is_a_hidden_div(panel_session):
    assert _html(panel_session) == (
        '<div id="pl" class="pjx-popover__panel" data-pjx-popover-panel hidden></div>'
    )


def test_as_form_false_matches_the_default(panel_session):
    assert _html(panel_session, as_form=False) == _html(panel_session)


def test_as_form_wraps_the_panel_in_a_form(panel_session):
    """A form panel lets the popover submit without an outer form; the closing tag has to match too."""
    html = _html(panel_session, as_form=True)
    assert html.startswith('<form id="pl"')
    assert html.endswith("</form>")
    assert "<div" not in html


def test_panel_is_hidden_so_the_js_owns_the_open_state(panel_session):
    assert " hidden>" in _html(panel_session)


def test_role_is_applied(panel_session):
    assert 'role="listbox"' in _html(panel_session, role="listbox")


def test_empty_role_omits_the_attribute(panel_session):
    assert "role=" not in _html(panel_session)


def test_class_name_appended_to_panel(panel_session):
    assert 'class="pjx-popover__panel mine"' in _html(panel_session, class_name="mine")


def test_string_content_is_interpolated(panel_session):
    assert ">body</div>" in _html(panel_session, content="body")


def test_invalid_role_is_rejected():
    with pytest.raises(ValidationError):
        PJXPopoverPanel(id="pl", role="banner")  # type: ignore[arg-type]


def test_dropped_behavior_field_is_rejected():
    """`behavior` did not survive the v2 port; extra="forbid" turns it into an error."""
    with pytest.raises(ValidationError):
        PJXPopoverPanel(id="pl", behavior=True)  # type: ignore[call-arg]


def test_dropped_extra_attrs_field_is_rejected():
    """`extra_attrs` did not survive the v2 port either (ADR 0006, strict core)."""
    with pytest.raises(ValidationError):
        PJXPopoverPanel(id="pl", extra_attrs={"data-x": "1"})  # type: ignore[call-arg]
