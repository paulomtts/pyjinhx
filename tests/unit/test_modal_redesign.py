import re

from pyjinhx.builtins import PJXModal


def _dialog(html: str) -> str:
    """Extract only the <dialog> element from a rendered component (strips inline script/style)."""
    m = re.search(r"<dialog[\s\S]*?</dialog>", html)
    return m.group(0) if m else html


def test_modal_contract_and_lifecycle_attrs():
    html = str(PJXModal(
        id="m1", title="T", body="B",
        close_label="Fechar", class_name="danger",
        extra_attrs={"data-x": "1"},
        open_on_mount=True, remove_on_close=True,
    ).render())
    assert 'class="pjx-modal danger"' in html
    assert 'aria-label="Fechar"' in html
    assert 'data-x="1"' in html
    assert "data-pjx-open-on-mount" in html
    assert "data-pjx-remove-on-close" in html
    assert "data-pjx-close" in html
    assert "onclick" not in html


def test_modal_defaults_omit_lifecycle_attrs():
    dialog = _dialog(str(PJXModal(id="m2", body="B").render()))
    assert "data-pjx-open-on-mount" not in dialog
    assert "data-pjx-remove-on-close" not in dialog
    assert 'aria-label="Close"' in dialog


def test_modal_close_content_defaults_to_glyph():
    dialog = _dialog(str(PJXModal(id="m3", body="B").render()))
    assert ">✕</button>" in dialog


def test_modal_close_content_is_configurable():
    dialog = _dialog(str(PJXModal(id="m4", body="B", close_content="Close me").render()))
    assert ">Close me</button>" in dialog
    assert "✕" not in dialog
