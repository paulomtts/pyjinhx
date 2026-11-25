"""Head assets must land even when the requesting element left the document.

Runs real htmx: htmx fires htmx:afterRequest on the requester, so a requester
that was swapped away before its response arrives never reaches pjx.js's
body listener. Only the xhr itself still knows the response is in.
"""

from __future__ import annotations

from pyjinhx.client import read_pjx_runtime, read_vendored_htmx

URL = "http://pjx.test/"
RESPONSE = (
    '<style data-pjx-asset="card.css" hx-swap-oob="beforeend:head">.c{color:red}</style>'
    '<div hx-swap-oob="beforeend:body"><i id="card"></i></div>'
)
PAGE = (
    '<html><head></head><body><div id="shell">'
    '<button id="btn" hx-post="/post" hx-swap="none">go</button></div></body></html>'
)
HEAD_TOKENS = (
    "() => Array.from(document.head.querySelectorAll('[data-pjx-asset]'))"
    ".map(n => n.getAttribute('data-pjx-asset'))"
)


def _open(page):
    page.route(
        URL,
        lambda route: route.fulfill(content_type="text/html", body=PAGE),
    )
    page.route(
        URL + "post",
        lambda route: route.fulfill(content_type="text/html", body=RESPONSE),
    )
    page.goto(URL)
    page.add_script_tag(content=read_vendored_htmx())
    page.add_script_tag(content=read_pjx_runtime())


def test_head_assets_apply_when_the_requester_is_detached_before_the_response(page):
    _open(page)
    page.evaluate(
        """() => document.body.addEventListener('htmx:beforeRequest', () => {
             document.getElementById('shell').remove();
           })"""
    )
    page.evaluate("document.getElementById('btn').click()")
    page.wait_for_selector("#card", state="attached")
    assert page.evaluate(HEAD_TOKENS) == ["card.css"]


def test_head_assets_apply_when_the_requester_is_still_attached(page):
    _open(page)
    page.evaluate("document.getElementById('btn').click()")
    page.wait_for_selector("#card", state="attached")
    assert page.evaluate(HEAD_TOKENS) == ["card.css"]
