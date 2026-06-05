from pyjinhx import BaseComponent


class Page(BaseComponent, base_layout=True):
    pass


class AdminPage(Page):  # subclass of a layout — should stay a layout
    pass


class PlainShell(BaseComponent):
    pass


def test_layout_root_injects_runtime_once():
    html = str(Page(id="page")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" in html
    assert "X-PJX-Mounted" in html
    assert html.count("htmx:configRequest") == 1


def test_non_layout_root_does_not_inject_runtime():
    html = str(PlainShell(id="shell")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" not in html


def test_base_layout_marker_is_set_and_inherited():
    assert getattr(Page, "_pjx_layout", False) is True
    assert getattr(AdminPage, "_pjx_layout", False) is True
    assert getattr(PlainShell, "_pjx_layout", False) is False
