import re

from pyjinhx.builtins import Notification


def _root(html: str) -> str:
    match = re.search(r"<div[^>]*px-notification[^>]*>", html)
    assert match, html
    return match.group(0)


def test_notification_autoshow_default_and_props():
    html = str(Notification(id="n1", content="Saved", dismiss_label="Fechar").render())
    assert "data-px-autoshow" in _root(html)
    assert 'aria-label="Fechar"' in html
    assert "data-px-close" in html
    assert "onclick" not in html


def test_notification_autoshow_off():
    html = str(Notification(id="n2", content="x", autoshow=False).render())
    assert "data-px-autoshow" not in _root(html)
