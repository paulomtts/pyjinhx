"""pjxInjectStyle(): one <style id="pjx-style"> per page, no matter how often it runs."""

from __future__ import annotations


def test_style_tag_is_injected_on_load(pjx_page):
    page = pjx_page("<div></div>")
    assert page.evaluate("!!document.getElementById('pjx-style')")


def test_style_defines_the_skeleton_and_spinner_classes(pjx_page):
    page = pjx_page("<div></div>")
    css = page.evaluate("document.getElementById('pjx-style').textContent")
    assert ".pjx-loading--skeleton" in css
    assert ".pjx-loading--spinner" in css


def test_style_rules_read_overridable_custom_properties(pjx_page):
    page = pjx_page("<div></div>")
    css = page.evaluate("document.getElementById('pjx-style').textContent")
    assert "--pjx-skeleton-color" in css
    assert "--pjx-spinner-size" in css


def test_reinjecting_keeps_a_single_style_tag(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate("pjx.injectStyle(); pjx.injectStyle()")
    assert page.evaluate("document.querySelectorAll('#pjx-style').length") == 1
