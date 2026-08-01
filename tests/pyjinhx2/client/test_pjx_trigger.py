"""pjxTrigger(): which mounted region a request came from, behind X-PJX-Trigger."""

from __future__ import annotations


def test_trigger_returns_nearest_mounted_ancestor(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="outer" data-pjx-type="Page" data-pjx-hash="h1">'
        '<div data-pjx-id="inner" data-pjx-type="Row" data-pjx-hash="h2">'
        '<button id="btn">go</button>'
        "</div></div>"
    )
    assert page.evaluate("pjx.trigger(document.getElementById('btn'))") == {"id": "inner"}


def test_trigger_matches_the_element_itself(pjx_page):
    page = pjx_page('<div id="btn" data-pjx-id="a1" data-pjx-type="Row" data-pjx-hash="h"></div>')
    assert page.evaluate("pjx.trigger(document.getElementById('btn'))") == {"id": "a1"}


def test_trigger_is_falsy_outside_any_mounted_region(pjx_page):
    page = pjx_page('<button id="btn">go</button>')
    assert not page.evaluate("pjx.trigger(document.getElementById('btn'))")


def test_trigger_is_falsy_for_a_missing_element(pjx_page):
    page = pjx_page("<div></div>")
    assert not page.evaluate("pjx.trigger(null)")
