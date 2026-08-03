"""Head assets arriving on an OOB swap: htmx drops head-targeted OOB, pjx.js applies them."""

from __future__ import annotations

SWAP_HTML = (
    '<style data-pjx-asset="card.css" hx-swap-oob="beforeend:head">.c{color:red}</style>'
    '<script data-pjx-asset="card.js" hx-swap-oob="beforeend:head">window.ran = true;</script>'
)

APPLY = "(html) => pjx.applyHeadAssets(html)"
HEAD_TOKENS = (
    "() => Array.from(document.head.querySelectorAll('[data-pjx-asset]'))"
    ".map(n => n.getAttribute('data-pjx-asset'))"
)


def test_new_assets_are_appended_to_head(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(APPLY, SWAP_HTML)
    assert sorted(page.evaluate(HEAD_TOKENS)) == ["card.css", "card.js"]


def test_appended_script_executes(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(APPLY, SWAP_HTML)
    assert page.evaluate("window.ran") is True


def test_asset_already_in_head_is_not_duplicated(pjx_page):
    page = pjx_page("<div></div>", head='<style data-pjx-asset="card.css"></style>')
    page.evaluate(APPLY, SWAP_HTML)
    assert page.evaluate(HEAD_TOKENS).count("card.css") == 1


def test_same_token_twice_in_one_response_is_applied_once(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(APPLY, SWAP_HTML + SWAP_HTML)
    assert page.evaluate(HEAD_TOKENS).count("card.css") == 1


def test_non_asset_markup_is_ignored(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(APPLY, '<div data-pjx-id="a1" hx-swap-oob="beforeend:head"></div>')
    assert page.evaluate(HEAD_TOKENS) == []


def test_unparseable_body_is_a_no_op(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(APPLY, "not html <<< at all")
    page.evaluate(APPLY, "")
    assert page.evaluate(HEAD_TOKENS) == []


def test_after_request_applies_assets_from_the_xhr(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(
        """
        (html) => document.body.dispatchEvent(new CustomEvent('htmx:afterRequest', {
          detail: { xhr: { responseText: html } }, bubbles: true
        }))
        """,
        SWAP_HTML,
    )
    assert sorted(page.evaluate(HEAD_TOKENS)) == ["card.css", "card.js"]


def test_after_request_without_an_xhr_is_a_no_op(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(
        """() => document.body.dispatchEvent(
             new CustomEvent('htmx:afterRequest', { detail: {}, bubbles: true })
           )"""
    )
    assert page.evaluate(HEAD_TOKENS) == []


def test_asset_tagged_link_is_not_applied(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(
        APPLY,
        '<link data-pjx-asset="card.css" rel="stylesheet" href="/card.css"'
        ' hx-swap-oob="beforeend:head">',
    )
    assert page.evaluate(HEAD_TOKENS) == []


def test_external_script_keeps_its_src(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(
        APPLY,
        '<script data-pjx-asset="card.js" src="/card.js"'
        ' hx-swap-oob="beforeend:head"></script>',
    )
    assert (
        page.evaluate(
            "() => document.head.querySelector('script[data-pjx-asset]')"
            ".getAttribute('src')"
        )
        == "/card.js"
    )
