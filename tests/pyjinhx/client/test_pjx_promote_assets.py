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
    page = pjx_page(
        '<style data-pjx-asset="card.css">.c{color:rgb(255, 0, 0)}</style><p class="c">x</p>'
    )
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


# A promoted builtin style must not land after app CSS already resident in
# <head> — same ordering guarantee as the OOB apply path.

HEAD_CSS_ORDER = (
    "() => Array.from(document.head.querySelectorAll('style[data-pjx-asset]'))"
    ".map(n => n.getAttribute('data-pjx-asset'))"
)


def test_promoted_builtin_style_is_inserted_before_resident_app_css(pjx_page):
    page = pjx_page(
        '<style data-pjx-asset="builtin.css" data-pjx-origin="builtin">'
        ".pjx-widget{padding:0}</style>",
        head='<style data-pjx-asset="app.css">.app{padding:8px}</style>',
    )
    assert page.evaluate(HEAD_CSS_ORDER) == ["builtin.css", "app.css"]

SWAP_IN_TOKENED_STYLE = """
() => {
  const region = document.querySelector('[data-pjx-id="badge"]');
  const style = document.createElement('style');
  style.setAttribute('data-pjx-asset', 'badge.css');
  style.textContent = '.badge{color:red}';
  region.after(style);
  document.body.dispatchEvent(new CustomEvent('htmx:afterSettle', { bubbles: true }));
}
"""


def test_style_swapped_in_after_init_is_promoted_on_settle(pjx_page):
    """A tokened style that arrives after init (an htmx fragment swap, not the
    cold render init already covers) must not wait for the next full load to
    reach <head> -- pjxPromoteInlineAssets has to run on every settle too."""
    page = pjx_page('<div data-pjx-id="badge"></div>')

    page.evaluate(SWAP_IN_TOKENED_STYLE)

    assert page.evaluate(HEAD_TOKENS) == ["badge.css"]
    assert page.evaluate(BODY_TOKENS) == []


def test_repeated_swaps_of_the_same_token_never_accumulate_in_the_body(pjx_page):
    """The polling-fragment case: the same component swaps in on every poll,
    each time grafting a fresh tokened <style> node into the body. Without a
    promote pass on every settle these pile up forever instead of being
    deduped against the copy already in <head>."""
    page = pjx_page('<div data-pjx-id="badge"></div>')

    for _ in range(5):
        page.evaluate(SWAP_IN_TOKENED_STYLE)

    assert page.evaluate(HEAD_TOKENS) == ["badge.css"]
    assert page.evaluate(BODY_TOKENS) == []
