import re

from pyjinhx.builtins import PageLoader


def _root(html: str) -> str:
    match = re.search(r"<div[^>]*px-page-loader[^>]*>", html)
    assert match, html
    return match.group(0)


def test_page_loader_config_attrs():
    html = str(PageLoader(id="pl", nav_targets="app-content,org-pane",
                          loading_label="Carregando").render())
    assert 'data-nav-targets="app-content,org-pane"' in html
    assert "px-page-loader--active" in _root(html)
    assert 'aria-label="Carregando"' in html


def test_page_loader_inactive_on_load():
    html = str(PageLoader(id="pl", active_on_load=False).render())
    assert "px-page-loader--active" not in _root(html)
