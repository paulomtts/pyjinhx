"""pjx.toast(): the dispatch half of the toast API — an L4 host renders it later."""

from __future__ import annotations

LISTEN = """
() => {
  window.__toasts = [];
  document.addEventListener('pjx:toast', (e) => window.__toasts.push(e.detail));
}
"""


def test_toast_dispatches_a_pjx_toast_event_carrying_the_payload(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(LISTEN)
    page.evaluate("pjx.toast({ message: 'saved', variant: 'success', duration: 3000 })")
    assert page.evaluate("window.__toasts") == [
        {"message": "saved", "variant": "success", "duration": 3000}
    ]


def test_toast_event_bubbles_from_document_to_window(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(
        "window.__seen = null;"
        "window.addEventListener('pjx:toast', (e) => {"
        "  window.__seen = { onWindow: true, targetIsDocument: e.target === document };"
        "})"
    )
    page.evaluate("pjx.toast({ message: 'hi' })")
    assert page.evaluate("window.__seen") == {"onWindow": True, "targetIsDocument": True}


def test_toast_without_a_listener_does_not_throw(pjx_page):
    page = pjx_page("<div></div>")
    assert page.evaluate("pjx.toast({ message: 'hi' }), 'ok'") == "ok"


def test_toast_with_no_payload_dispatches_an_empty_detail(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(LISTEN)
    page.evaluate("pjx.toast()")
    assert page.evaluate("window.__toasts") == [{}]
