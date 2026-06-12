import re

from pyjinhx.builtins import Modal


def _dialog(html: str) -> str:
    """Extract only the <dialog> element from a rendered component (strips inline script/style)."""
    m = re.search(r"<dialog[\s\S]*?</dialog>", html)
    return m.group(0) if m else html


def test_modal_contract_and_lifecycle_attrs():
    html = str(Modal(
        id="m1", title="T", body="B",
        close_label="Fechar", class_name="danger",
        extra_attrs={"data-x": "1"},
        open_on_mount=True, remove_on_close=True,
    ).render())
    assert 'class="px-modal danger"' in html
    assert 'aria-label="Fechar"' in html
    assert 'data-x="1"' in html
    assert "data-px-open-on-mount" in html
    assert "data-px-remove-on-close" in html
    assert "data-px-close" in html
    assert "onclick" not in html


def test_modal_defaults_omit_lifecycle_attrs():
    dialog = _dialog(str(Modal(id="m2", body="B").render()))
    assert "data-px-open-on-mount" not in dialog
    assert "data-px-remove-on-close" not in dialog
    assert 'aria-label="Close"' in dialog


def test_modal_close_content_defaults_to_glyph():
    dialog = _dialog(str(Modal(id="m3", body="B").render()))
    assert ">✕</button>" in dialog


def test_modal_close_content_is_configurable():
    dialog = _dialog(str(Modal(id="m4", body="B", close_content="Close me").render()))
    assert ">Close me</button>" in dialog
    assert "✕" not in dialog
