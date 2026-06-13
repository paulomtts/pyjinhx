import re

from pyjinhx.builtins import PJXNotification


def _root(html: str) -> str:
    match = re.search(r"<div[^>]*pjx-notification[^>]*>", html)
    assert match, html
    return match.group(0)


def test_notification_autoshow_default_and_props():
    html = str(PJXNotification(id="n1", content="Saved", dismiss_label="Fechar").render())
    assert "data-pjx-autoshow" in _root(html)
    assert 'aria-label="Fechar"' in html
    assert "data-pjx-close" in html
    assert "onclick" not in html


def test_notification_autoshow_off():
    html = str(PJXNotification(id="n2", content="x", autoshow=False).render())
    assert "data-pjx-autoshow" not in _root(html)
