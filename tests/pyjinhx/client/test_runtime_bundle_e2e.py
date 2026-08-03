"""One cold-render payload, no component includes: indicators still work."""

from __future__ import annotations

from pyjinhx.assets import emit_assets
from pyjinhx.client.inject import inject_runtime
from pyjinhx.session import RenderSession

BODY = (
    '<div data-pjx-id="t" data-pjx-reacts="count" data-pjx-loading="skeleton">'
    '<button id="btn"></button></div>'
)

FIRE = """
() => {
  const elt = document.querySelector('#btn');
  const xhr = { handlers: [], addEventListener(t, fn) { this.handlers.push([t, fn]); },
                loadend() { this.handlers.forEach(([t, fn]) => t === 'loadend' && fn()); } };
  window.__xhr = xhr;
  elt.dispatchEvent(new CustomEvent('htmx:beforeRequest',
    { bubbles: true, cancelable: true, detail: { elt: elt, xhr: xhr } }));
}
"""


def test_inject_runtime_payload_alone_drives_the_loading_indicator(page):
    session = RenderSession()
    inject_runtime(session)
    # Runtime payload at the end of <body>, mirroring real usage: a <script>
    # placed in <head> would execute before document.body exists, which trips
    # pjxPromoteInlineAssets's null check -- an unrelated, out-of-scope bug in
    # head-asset relocation, not something #675 touches.
    page.set_content(f"<body>{BODY}{emit_assets(session)}</body>")

    page.evaluate(FIRE)
    assert page.evaluate(
        "document.querySelector('[data-pjx-id=\"t\"]').className"
    ) == "pjx-loading--skeleton"
    assert page.evaluate(
        "getComputedStyle(document.querySelector('[data-pjx-id=\"t\"]')).pointerEvents"
    ) == "none"

    page.evaluate("window.__xhr.loadend()")
    assert page.evaluate("document.querySelector('[data-pjx-id=\"t\"]').className") == ""


def test_inject_runtime_payload_alone_drives_the_page_loader(page):
    session = RenderSession()
    inject_runtime(session)
    page.set_content(f"<body>{BODY}{emit_assets(session)}</body>")

    page.evaluate("pjx.loader.page(true)")
    assert page.evaluate("document.documentElement.className") == "pjx-loading--page"
    page.evaluate("pjx.loader.page(false)")
    assert page.evaluate("document.documentElement.className") == ""
