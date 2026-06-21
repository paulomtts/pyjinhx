"""Migrated drawer contract tests — now using the composable API.

The old PJXDrawer(title=, body=, footer=, close_label=, extra_attrs=) API was
removed. These tests verify equivalent behaviour via the composed parts.
"""

import re

from pyjinhx.builtins import PJXDrawer, PJXDrawerBody, PJXDrawerHeader


def _dialog(html: str) -> str:
    """Extract only the <dialog> element from a rendered component (strips inline script/style)."""
    m = re.search(r"<dialog[\s\S]*?</dialog>", html)
    return m.group(0) if m else html


def test_drawer_contract_and_lifecycle_attrs():
    header = str(PJXDrawerHeader(id="d1-h", title="T", close_label="Fechar").render())
    body = str(PJXDrawerBody(id="d1-b", content="B").render())
    html = str(PJXDrawer(
        id="d1",
        class_name="wide",
        open_on_mount=True,
        remove_on_close=True,
        content=header + body,
    ).render())
    assert 'class="pjx-drawer pjx-drawer--right wide"' in html
    assert 'aria-label="Fechar"' in html
    assert "data-pjx-open-on-mount" in html
    assert "data-pjx-remove-on-close" in html
    assert "data-pjx-close" in html
    assert "onclick" not in html


def test_drawer_defaults_omit_lifecycle_attrs():
    body = str(PJXDrawerBody(id="d2-b", content="B").render())
    dialog = _dialog(str(PJXDrawer(id="d2", content=body).render()))
    assert "data-pjx-open-on-mount" not in dialog
    assert "data-pjx-remove-on-close" not in dialog
