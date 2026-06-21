"""Tests for the new composable PJXModal shell."""
import re

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXModal, PJXModalBody, PJXModalFooter, PJXModalHeader


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _dialog(html: str) -> str:
    """Extract only the <dialog> element (strips inline script/style)."""
    m = re.search(r"<dialog[\s\S]*?</dialog>", html)
    return m.group(0) if m else html


# ── Shell contract ────────────────────────────────────────────────────────────

def test_modal_shell_single_dialog():
    html = str(PJXModal(id="m1").render())
    assert html.count("<dialog") == 1


def test_modal_shell_has_box():
    html = str(PJXModal(id="m2").render())
    assert 'class="pjx-modal__box"' in html


def test_modal_shell_class():
    html = str(PJXModal(id="m3").render())
    assert 'class="pjx-modal"' in html


def test_modal_shell_class_name():
    html = str(PJXModal(id="m4", class_name="danger").render())
    assert 'class="pjx-modal danger"' in html


def test_modal_open_on_mount():
    dialog = _dialog(str(PJXModal(id="m5", open_on_mount=True).render()))
    assert "data-pjx-open-on-mount" in dialog


def test_modal_open_on_mount_absent_by_default():
    dialog = _dialog(str(PJXModal(id="m6").render()))
    assert "data-pjx-open-on-mount" not in dialog


def test_modal_remove_on_close():
    dialog = _dialog(str(PJXModal(id="m7", remove_on_close=True).render()))
    assert "data-pjx-remove-on-close" in dialog


def test_modal_remove_on_close_absent_by_default():
    dialog = _dialog(str(PJXModal(id="m8").render()))
    assert "data-pjx-remove-on-close" not in dialog


def test_modal_old_api_fields_gone():
    """title/header/body/footer/close_label/close_content must not exist on PJXModal."""
    for field in ("title", "header", "body", "footer", "close_label", "close_content"):
        assert field not in PJXModal.model_fields, f"Unexpected field '{field}' on PJXModal"


# ── Composed modal ────────────────────────────────────────────────────────────

def _composed(tmp_path=None) -> str:
    header = str(PJXModalHeader(id="cm-h", title="Delete file?").render())
    body = str(PJXModalBody(id="cm-b", content="This cannot be undone.").render())
    footer = str(PJXModalFooter(id="cm-f", content="<button>OK</button>").render())
    return str(PJXModal(id="cm", content=header + body + footer).render())


def test_composed_modal_order(tmp_path):
    html = _composed()
    header_pos = html.index("pjx-modal__header")
    body_pos = html.index("pjx-modal__body")
    footer_pos = html.index("pjx-modal__footer")
    assert header_pos < body_pos < footer_pos


def test_composed_modal_has_close_button(tmp_path):
    html = _composed()
    assert "data-pjx-close" in html


def test_composed_modal_single_dialog(tmp_path):
    html = _composed()
    assert html.count("<dialog") == 1
