"""PJXPopoverTrigger renders the clickable element that toggles its popover panel (port of v0.x pyjinhx/builtins/ui/pjx_popover/pjx_popover_trigger.html)."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_popover_trigger import PJXPopoverTrigger
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def trigger_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXPopoverTrigger(id="t", **kw), session)


def test_default_render_is_a_collapsed_button(trigger_session):
    assert _html(trigger_session) == (
        '<button id="t" class="pjx-popover__trigger" type="button"'
        ' data-pjx-toggle aria-expanded="false"></button>'
    )


def test_div_tag_gets_button_semantics_by_hand(trigger_session):
    """A div trigger has to carry role/tabindex itself; the JS keyboard handler keys off exactly this shape."""
    html = _html(trigger_session, tag="div")
    assert html.startswith('<div id="t"')
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
    assert "type=" not in html
    assert html.endswith("</div>")


def test_role_becomes_aria_haspopup(trigger_session):
    assert 'aria-haspopup="menu"' in _html(trigger_session, role="menu")


def test_empty_role_omits_aria_haspopup(trigger_session):
    assert "aria-haspopup" not in _html(trigger_session)


def test_class_name_appended_to_trigger(trigger_session):
    assert 'class="pjx-popover__trigger mine"' in _html(
        trigger_session, class_name="mine"
    )


def test_string_content_is_interpolated(trigger_session):
    assert ">Open</button>" in _html(trigger_session, content="Open")


def test_invalid_tag_is_rejected():
    with pytest.raises(ValidationError):
        PJXPopoverTrigger(id="t", tag="span")


def test_invalid_role_is_rejected():
    with pytest.raises(ValidationError):
        PJXPopoverTrigger(id="t", role="banner")


def test_dropped_behavior_field_is_rejected():
    """`behavior` did not survive the v2 port; extra="forbid" turns it into an error."""
    with pytest.raises(ValidationError):
        PJXPopoverTrigger(id="t", behavior=True)


def test_dropped_extra_attrs_field_is_rejected():
    """`extra_attrs` did not survive the v2 port either (ADR 0006, strict core)."""
    with pytest.raises(ValidationError):
        PJXPopoverTrigger(id="t", extra_attrs={"data-x": "1"})
