"""PJXConfirmDialog renders the single-root <dialog> confirm shell; its message text and open/close come from pjx.confirm(), not from fields."""

import pytest
from pydantic import ValidationError

from pyjinhx import builtins
from pyjinhx.builtins.ui.pjx_confirm_dialog import PJXConfirmDialog
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

EXPECTED_DEFAULT = (
    '<dialog id="cd" class="pjx-confirm-dialog" data-pjx-dialog="confirm" aria-modal="true" aria-labelledby="cd-message">\n'
    '    <div class="pjx-confirm-dialog__card">\n'
    '        <p id="cd-message" class="pjx-confirm-dialog__message"></p>\n'
    '        <div class="pjx-confirm-dialog__actions">\n'
    '            <button type="button" class="pjx-confirm-dialog__cancel">Cancel</button>\n'
    '            <button type="button" class="pjx-confirm-dialog__ok">Confirm</button>\n'
    "        </div>\n"
    "    </div>\n"
    "</dialog>"
)


@pytest.fixture
def confirm_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXConfirmDialog(id="cd", **kw), session)


def test_default_render_is_single_confirm_dialog(confirm_session):
    assert _html(confirm_session) == EXPECTED_DEFAULT


def test_id_renders_on_the_dialog(confirm_session):
    html = _html(confirm_session)
    assert '<dialog id="cd"' in html
    assert 'data-pjx-dialog="confirm"' in html


def test_class_name_appended_to_root(confirm_session):
    assert 'class="pjx-confirm-dialog mine"' in _html(
        confirm_session, class_name="mine"
    )


def test_empty_class_name_adds_nothing(confirm_session):
    assert 'class="pjx-confirm-dialog"' in _html(confirm_session, class_name="")


def test_confirm_label_renders_on_ok_button(confirm_session):
    html = _html(confirm_session, confirm_label="Delete")
    assert (
        '<button type="button" class="pjx-confirm-dialog__ok">Delete</button>' in html
    )


def test_cancel_label_renders_on_cancel_button(confirm_session):
    html = _html(confirm_session, cancel_label="Nope")
    assert (
        '<button type="button" class="pjx-confirm-dialog__cancel">Nope</button>' in html
    )


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): only extra_attrs may pass extra attributes through."""
    with pytest.raises(ValidationError):
        PJXConfirmDialog(id="cd", data_k="v")  # pyright: ignore[reportCallIssue]


def test_extra_attrs_round_trip_onto_the_dialog(confirm_session):
    html = _html(confirm_session, extra_attrs={"data-testid": "confirm"})
    assert 'data-testid="confirm"' in html
    assert html == EXPECTED_DEFAULT.replace(
        'aria-labelledby="cd-message">',
        'aria-labelledby="cd-message" data-testid="confirm">',
    )


def test_exported_from_the_builtins_namespace():
    """`from pyjinhx.builtins import PJXConfirmDialog` must resolve through the lazy export table."""
    assert "PJXConfirmDialog" in builtins.__all__
    assert builtins.PJXConfirmDialog is PJXConfirmDialog  # pyright: ignore[reportAttributeAccessIssue]
