"""Cold-render inline <style data-pjx-asset> must move to <head> to survive swaps."""

from __future__ import annotations

HEAD_TOKENS = (
    "() => Array.from(document.head.querySelectorAll('[data-pjx-asset]'))"
    ".map(n => n.getAttribute('data-pjx-asset'))"
)
BODY_TOKENS = (
    "() => Array.from(document.body.querySelectorAll('[data-pjx-asset]'))"
    ".map(n => n.getAttribute('data-pjx-asset'))"
)


def test_body_style_is_promoted_on_load(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1"><style data-pjx-asset="card.css">.c{color:red}</style></div>'
    )
    assert page.evaluate(HEAD_TOKENS) == ["card.css"]
    assert page.evaluate(BODY_TOKENS) == []


def test_promoted_style_keeps_its_css(pjx_page):
    page = pjx_page('<style data-pjx-asset="card.css">.c{color:rgb(255, 0, 0)}</style><p class="c">x</p>')
    color = page.evaluate("() => getComputedStyle(document.querySelector('.c')).color")
    assert color == "rgb(255, 0, 0)"


def test_duplicate_of_a_head_resident_token_is_dropped(pjx_page):
    page = pjx_page(
        '<style data-pjx-asset="card.css">.c{color:blue}</style>',
        head='<style data-pjx-asset="card.css">.c{color:red}</style>',
    )
    assert page.evaluate(HEAD_TOKENS) == ["card.css"]
    assert page.evaluate(BODY_TOKENS) == []


def test_body_scripts_are_left_alone(pjx_page):
    page = pjx_page('<script data-pjx-asset="card.js"></script>')
    assert page.evaluate(HEAD_TOKENS) == []
    assert page.evaluate(BODY_TOKENS) == ["card.js"]
