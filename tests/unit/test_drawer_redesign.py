import re

from pyjinhx.builtins import Drawer


def _dialog(html: str) -> str:
    """Extract only the <dialog> element from a rendered component (strips inline script/style)."""
    m = re.search(r"<dialog[\s\S]*?</dialog>", html)
    return m.group(0) if m else html


def test_drawer_contract_and_lifecycle_attrs():
    html = str(Drawer(
        id="d1", title="T", body="B",
        close_label="Fechar", class_name="wide",
        extra_attrs={"data-x": "1"},
        open_on_mount=True, remove_on_close=True,
    ).render())
    assert 'class="px-drawer px-drawer--right wide"' in html
    assert 'aria-label="Fechar"' in html
    assert 'data-x="1"' in html
    assert "data-px-open-on-mount" in html
    assert "data-px-remove-on-close" in html
    assert "data-px-close" in html
    assert "onclick" not in html


def test_drawer_defaults_omit_lifecycle_attrs():
    dialog = _dialog(str(Drawer(id="d2", body="B").render()))
    assert "data-px-open-on-mount" not in dialog
    assert "data-px-remove-on-close" not in dialog
    assert 'aria-label="Close"' in dialog
