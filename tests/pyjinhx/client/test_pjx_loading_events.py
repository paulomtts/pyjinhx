"""Core pjx.js emits loading events; it never writes classList itself."""

from __future__ import annotations

FIRE = """
(arg) => {
  const elt = document.querySelector(arg.trigger);
  const xhr = { handlers: [], addEventListener(t, fn) { this.handlers.push([t, fn]); },
                loadend() { this.handlers.forEach(([t, fn]) => t === 'loadend' && fn()); } };
  window.__xhrs = window.__xhrs || {};
  window.__xhrs[arg.name] = xhr;
  const evt = new CustomEvent('htmx:beforeRequest',
    { bubbles: true, cancelable: true, detail: { elt: elt, xhr: xhr } });
  elt.dispatchEvent(evt);
}
"""

RECORD = """
() => {
  window.__evts = [];
  ['pjx:region-loading-start', 'pjx:region-loading-end',
   'pjx:page-loading-start', 'pjx:page-loading-end'].forEach((name) => {
    document.addEventListener(name, (e) => {
      window.__evts.push([name, e.detail && e.detail.id]);
    });
  });
}
"""

BODY = (
    '<div data-pjx-id="t" data-pjx-reacts="count" data-pjx-loading="skeleton">'
    '<button id="btn"></button></div>'
)


def test_beforerequest_dispatches_region_loading_start(pjx_page):
    page = pjx_page(BODY)
    page.evaluate(RECORD)
    page.evaluate(FIRE, {"trigger": "#btn", "name": "a"})
    assert page.evaluate("window.__evts") == [["pjx:region-loading-start", "t"]]


def test_core_alone_never_applies_the_loading_class(pjx_page):
    page = pjx_page(BODY)
    page.evaluate(FIRE, {"trigger": "#btn", "name": "a"})
    assert (
        page.evaluate("document.querySelector('[data-pjx-id=\"t\"]').className") == ""
    )


def test_completion_dispatches_region_loading_end(pjx_page):
    page = pjx_page(BODY)
    page.evaluate(FIRE, {"trigger": "#btn", "name": "a"})
    page.evaluate(RECORD)
    page.evaluate("window.__xhrs.a.loadend()")
    assert page.evaluate("window.__evts") == [["pjx:region-loading-end", "t"]]


def test_loader_page_dispatches_start_and_end_with_ref_counting(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(RECORD)
    page.evaluate(
        "pjx.loader.page(true); pjx.loader.page(true); pjx.loader.page(false)"
    )
    assert page.evaluate("window.__evts") == [
        ["pjx:page-loading-start", None],
        ["pjx:page-loading-start", None],
    ]
    page.evaluate("pjx.loader.page(false)")
    assert page.evaluate("window.__evts")[-1] == ["pjx:page-loading-end", None]


def test_core_alone_never_sets_the_page_loading_class(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate("pjx.loader.page(true)")
    assert page.evaluate("document.documentElement.className") == ""


def test_page_false_from_zero_never_dispatches_an_end_event(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(RECORD)
    page.evaluate("pjx.loader.page(false)")
    assert page.evaluate("window.__evts") == []
