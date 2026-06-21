"""Tests for PJXDrawerHeader."""

from pyjinhx.builtins import PJXDrawerHeader


def test_header_renders_header_element():
    html = str(PJXDrawerHeader(id="h1").render())
    assert "<header" in html
    assert 'class="pjx-drawer__header"' in html


def test_header_stamps_id():
    html = str(PJXDrawerHeader(id="hdr-main").render())
    assert 'id="hdr-main"' in html


def test_header_with_class_name():
    html = str(PJXDrawerHeader(id="h2", class_name="sticky").render())
    assert 'class="pjx-drawer__header sticky"' in html


def test_header_title_renders_span():
    html = str(PJXDrawerHeader(id="h3", title="Menu").render())
    assert '<span class="pjx-drawer__title">Menu</span>' in html


def test_header_without_title_renders_content():
    html = str(PJXDrawerHeader(id="h4", content="<strong>Nav</strong>").render())
    assert "<strong>Nav</strong>" in html
    assert '<span class="pjx-drawer__title">' not in html


def test_header_close_button_always_present():
    html = str(PJXDrawerHeader(id="h5").render())
    assert 'class="pjx-drawer__close"' in html
    assert "data-pjx-close" in html


def test_header_close_button_aria_label_default():
    html = str(PJXDrawerHeader(id="h6").render())
    assert 'aria-label="Close"' in html


def test_header_custom_close_label():
    html = str(PJXDrawerHeader(id="h7", close_label="Fechar").render())
    assert 'aria-label="Fechar"' in html


def test_header_default_close_content():
    html = str(PJXDrawerHeader(id="h8").render())
    assert "✕" in html


def test_header_close_button_type():
    html = str(PJXDrawerHeader(id="h9").render())
    assert 'type="button"' in html
