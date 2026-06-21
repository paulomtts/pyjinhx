"""Tests for PJXDrawerBody and PJXDrawerFooter."""

import pytest

from pyjinhx.builtins import PJXDrawerBody, PJXDrawerFooter


def test_drawer_body_renders_div():
    html = str(PJXDrawerBody(id="b1", content="Hello").render())
    assert "<div" in html
    assert 'class="pjx-drawer__body"' in html
    assert "Hello" in html


def test_drawer_body_with_class_name():
    html = str(PJXDrawerBody(id="b2", class_name="extra", content="X").render())
    assert 'class="pjx-drawer__body extra"' in html


def test_drawer_body_stamps_id():
    html = str(PJXDrawerBody(id="body-main", content="").render())
    assert 'id="body-main"' in html


def test_drawer_body_empty_content():
    html = str(PJXDrawerBody(id="b3").render())
    assert 'class="pjx-drawer__body"' in html


def test_drawer_footer_renders_footer():
    html = str(PJXDrawerFooter(id="f1", content="Footer text").render())
    assert "<footer" in html
    assert 'class="pjx-drawer__footer"' in html
    assert "Footer text" in html


def test_drawer_footer_with_class_name():
    html = str(PJXDrawerFooter(id="f2", class_name="sticky", content="Save").render())
    assert 'class="pjx-drawer__footer sticky"' in html


def test_drawer_footer_stamps_id():
    html = str(PJXDrawerFooter(id="footer-main", content="").render())
    assert 'id="footer-main"' in html


def test_drawer_footer_empty_content():
    html = str(PJXDrawerFooter(id="f3").render())
    assert 'class="pjx-drawer__footer"' in html
