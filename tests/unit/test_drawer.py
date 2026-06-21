"""Tests for the new composable PJXDrawer shell."""

import re

from pyjinhx.builtins import PJXDrawer, PJXDrawerBody, PJXDrawerFooter, PJXDrawerHeader


def _dialog(html: str) -> str:
    """Extract the <dialog> element (strips assets like style/script)."""
    m = re.search(r"<dialog[\s\S]*?</dialog>", html)
    return m.group(0) if m else html


def test_drawer_renders_single_dialog():
    html = str(PJXDrawer(id="d1").render())
    assert html.count("<dialog") == 1
    assert html.count("</dialog>") == 1


def test_drawer_default_side_right():
    dialog = _dialog(str(PJXDrawer(id="d2").render()))
    assert 'class="pjx-drawer pjx-drawer--right"' in dialog


def test_drawer_side_left():
    dialog = _dialog(str(PJXDrawer(id="d3", side="left").render()))
    assert "pjx-drawer--left" in dialog


def test_drawer_side_bottom():
    dialog = _dialog(str(PJXDrawer(id="d4", side="bottom").render()))
    assert "pjx-drawer--bottom" in dialog


def test_drawer_box_div_present():
    dialog = _dialog(str(PJXDrawer(id="d5").render()))
    assert 'class="pjx-drawer__box"' in dialog


def test_drawer_open_on_mount_attr():
    dialog = _dialog(str(PJXDrawer(id="d6", open_on_mount=True).render()))
    assert "data-pjx-open-on-mount" in dialog


def test_drawer_remove_on_close_attr():
    dialog = _dialog(str(PJXDrawer(id="d7", remove_on_close=True).render()))
    assert "data-pjx-remove-on-close" in dialog


def test_drawer_defaults_omit_lifecycle_attrs():
    dialog = _dialog(str(PJXDrawer(id="d8").render()))
    assert "data-pjx-open-on-mount" not in dialog
    assert "data-pjx-remove-on-close" not in dialog


def test_drawer_class_name():
    dialog = _dialog(str(PJXDrawer(id="d9", class_name="wide").render()))
    assert 'class="pjx-drawer pjx-drawer--right wide"' in dialog


def test_drawer_stamps_id():
    dialog = _dialog(str(PJXDrawer(id="nav-drawer").render()))
    assert 'id="nav-drawer"' in dialog


def test_drawer_removed_fields_not_in_model():
    fields = PJXDrawer.model_fields
    for removed in ("title", "body", "footer", "close_label", "close_content", "extra_attrs"):
        assert removed not in fields, f"removed field '{removed}' still in PJXDrawer.model_fields"


def test_drawer_composition_order():
    header = str(PJXDrawerHeader(id="h1", title="Menu").render())
    body = str(PJXDrawerBody(id="b1", content="Links here").render())
    footer = str(PJXDrawerFooter(id="f1", content="v1.0").render())
    composed = header + body + footer
    html = str(PJXDrawer(id="d10", content=composed).render())
    dialog = _dialog(html)
    assert dialog.index("pjx-drawer__header") < dialog.index("pjx-drawer__body") < dialog.index("pjx-drawer__footer")


def test_drawer_close_button_in_composed_drawer():
    header = str(PJXDrawerHeader(id="h2", title="Nav").render())
    body = str(PJXDrawerBody(id="b2", content="Items").render())
    html = str(PJXDrawer(id="d11", content=header + body).render())
    assert "data-pjx-close" in html


def test_drawer_no_onclick():
    html = str(PJXDrawer(id="d12", open_on_mount=True).render())
    dialog = _dialog(html)
    assert "onclick" not in dialog
