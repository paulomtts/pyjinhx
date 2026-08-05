"""PJXPromptDialog renders the single-root <dialog> prompt shell; its question, initial value and open/close come from pjx.prompt(), not from fields."""

import pytest
from pydantic import ValidationError

from pyjinhx import builtins
from pyjinhx.builtins.ui.pjx_prompt_dialog import PJXPromptDialog
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

EXPECTED_DEFAULT = (
    '<dialog id="pd" class="pjx-prompt-dialog" data-pjx-dialog="prompt" aria-modal="true" aria-labelledby="pd-label">\n'
    '    <form method="dialog" class="pjx-prompt-dialog__card">\n'
    '        <label id="pd-label" class="pjx-prompt-dialog__label" for="pd-input"></label>\n'
    '        <input id="pd-input" class="pjx-prompt-dialog__input" type="text" autocomplete="off" />\n'
    '        <div class="pjx-prompt-dialog__actions">\n'
    '            <button type="button" class="pjx-prompt-dialog__cancel">Cancel</button>\n'
    '            <button type="submit" class="pjx-prompt-dialog__ok">OK</button>\n'
    "        </div>\n"
    "    </form>\n"
    "</dialog>"
)


@pytest.fixture
def prompt_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXPromptDialog(id="pd", **kw), session)


def test_default_render_is_single_prompt_dialog(prompt_session):
    assert _html(prompt_session) == EXPECTED_DEFAULT


def test_id_renders_on_the_dialog(prompt_session):
    html = _html(prompt_session)
    assert '<dialog id="pd"' in html
    assert 'data-pjx-dialog="prompt"' in html


def test_class_name_appended_to_root(prompt_session):
    assert 'class="pjx-prompt-dialog mine"' in _html(prompt_session, class_name="mine")


def test_empty_class_name_adds_nothing(prompt_session):
    assert 'class="pjx-prompt-dialog"' in _html(prompt_session, class_name="")


def test_submit_label_renders_on_submit_button(prompt_session):
    html = _html(prompt_session, submit_label="Rename")
    assert '<button type="submit" class="pjx-prompt-dialog__ok">Rename</button>' in html


def test_cancel_label_renders_on_cancel_button(prompt_session):
    html = _html(prompt_session, cancel_label="Nope")
    assert (
        '<button type="button" class="pjx-prompt-dialog__cancel">Nope</button>' in html
    )


def test_input_label_renders_on_label(prompt_session):
    html = _html(prompt_session, input_label="New name")
    assert (
        '<label id="pd-label" class="pjx-prompt-dialog__label" for="pd-input">New name</label>'
        in html
    )


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone."""
    with pytest.raises(ValidationError):
        PJXPromptDialog(id="pd", extra_attrs={"data-k": "v"})  # pyright: ignore[reportCallIssue]


def test_exported_from_the_builtins_namespace():
    """`from pyjinhx.builtins import PJXPromptDialog` must resolve through the lazy export table."""
    assert "PJXPromptDialog" in builtins.__all__
    assert builtins.PJXPromptDialog is PJXPromptDialog  # pyright: ignore[reportAttributeAccessIssue]
