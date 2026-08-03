"""PJXModal renders the single-root <dialog> shell that composes the modal parts (port of v0.x pyjinhx/builtins/ui/pjx_modal)."""

import dataclasses

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_modal import PJXModal
from pyjinhx.builtins.ui.pjx_modal_body import PJXModalBody
from pyjinhx.builtins.ui.pjx_modal_footer import PJXModalFooter
from pyjinhx.builtins.ui.pjx_modal_header import PJXModalHeader
from pyjinhx.component import BaseComponent, Slot
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def modal_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXModal(id="m", **kw), session)


def test_default_render_is_single_dialog_with_box(modal_session):
    html = _html(modal_session)
    assert (
        html
        == '<dialog class="pjx-modal" id="m"><div class="pjx-modal__box"></div></dialog>'
    )


def test_id_renders_on_the_dialog(modal_session):
    assert '<dialog class="pjx-modal" id="m"' in _html(modal_session)


def test_class_name_appended_to_root(modal_session):
    assert 'class="pjx-modal mine"' in _html(modal_session, class_name="mine")


def test_empty_class_name_adds_nothing(modal_session):
    assert 'class="pjx-modal"' in _html(modal_session, class_name="")


def test_open_on_mount_emits_data_attribute(modal_session):
    assert "data-pjx-open-on-mount" in _html(modal_session, open_on_mount=True)


def test_open_on_mount_default_omits_data_attribute(modal_session):
    assert "data-pjx-open-on-mount" not in _html(modal_session, open_on_mount=False)


def test_remove_on_close_emits_data_attribute(modal_session):
    assert "data-pjx-remove-on-close" in _html(modal_session, remove_on_close=True)


def test_remove_on_close_default_omits_data_attribute(modal_session):
    assert "data-pjx-remove-on-close" not in _html(modal_session, remove_on_close=False)


def test_component_content_renders_inside_the_box(modal_session):
    html = _html(modal_session, content=PJXModalBody(id="b", content="Confirm?"))
    assert html.count("<dialog") == 1
    assert html.index("pjx-modal__box") < html.index("pjx-modal__body")
    assert "Confirm?" in html


def test_string_content_renders_raw_inside_root(modal_session):
    """ADR 0003: a plain str in a Slot is authored markup, not escaped."""
    html = _html(modal_session, content="<p>raw</p>")
    assert html.count("<dialog") == 1
    assert "<p>raw</p>" in html


def test_clean_break_removed_fields():
    """v0.x already dropped these from the shell (they live on the parts); v2 must not reintroduce them."""
    for gone in ("title", "header", "body", "footer", "close_label", "close_content"):
        assert gone not in PJXModal.model_fields


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone."""
    with pytest.raises(ValidationError):
        PJXModal(id="m", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]


class ModalHost(BaseComponent):
    """A three-slot host, so header/body/footer compose in one tree without string joins.

    Mirrors CardHost in tests/pyjinhx/builtins/pjx_card/test_pjx_card.py: a bare
    `{{ content }}` interpolation never iterates a list, so three named slots is
    the proven multi-child shape.
    """

    head: Slot = ""
    body: Slot = ""
    foot: Slot = ""


@pytest.fixture
def modal_host_dir(tmp_path):
    """Give ModalHost a real template on disk and repoint its descriptor at it.

    A class defined ad hoc in a test module resolves a template candidate
    co-located with the test file, which does not exist — rendering would raise
    TemplateNotFound. Same fixture shape as pjx_card's `card_host_dir`.
    """
    host_path = tmp_path / "modal_host.pjx"
    host_path.write_text(
        '<div id="{{ id }}" class="modal-host">{{ head }}{{ body }}{{ foot }}</div>'
    )
    ModalHost.__pjx_descriptor__ = dataclasses.replace(
        ModalHost.__pjx_descriptor__, template_path=host_path
    )
    yield tmp_path


def test_composition_order_header_body_footer(modal_session, modal_host_dir):
    """Header, body and footer render in document order inside one dialog root."""
    html = render(
        PJXModal(
            id="m",
            content=ModalHost(
                id="host",
                head=PJXModalHeader(id="h", title="Delete file?"),
                body=PJXModalBody(id="b", content="This cannot be undone."),
                foot=PJXModalFooter(id="f", content="Cancel / Delete"),
            ),
        ),
        modal_session,
    )
    assert html.count("<dialog") == 1
    assert (
        html.index("pjx-modal__header")
        < html.index("pjx-modal__body")
        < html.index("pjx-modal__footer")
    )
    assert "Delete file?" in html
    assert "This cannot be undone." in html
    assert "Cancel / Delete" in html
