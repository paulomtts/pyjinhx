import re

from pyjinhx.builtins import PJXDrawer


def _dialog(html: str) -> str:
    """Extract only the <dialog> element from a rendered component (strips inline script/style)."""
    m = re.search(r"<dialog[\s\S]*?</dialog>", html)
    return m.group(0) if m else html


def test_drawer_contract_and_lifecycle_attrs():
    html = str(PJXDrawer(
        id="d1", title="T", body="B",
        close_label="Fechar", class_name="wide",
        extra_attrs={"data-x": "1"},
        open_on_mount=True, remove_on_close=True,
    ).render())
    assert 'class="pjx-drawer pjx-drawer--right wide"' in html
    assert 'aria-label="Fechar"' in html
    assert 'data-x="1"' in html
    assert "data-pjx-open-on-mount" in html
    assert "data-pjx-remove-on-close" in html
    assert "data-pjx-close" in html
    assert "onclick" not in html


def test_drawer_defaults_omit_lifecycle_attrs():
    dialog = _dialog(str(PJXDrawer(id="d2", body="B").render()))
    assert "data-pjx-open-on-mount" not in dialog
    assert "data-pjx-remove-on-close" not in dialog
    assert 'aria-label="Close"' in dialog
