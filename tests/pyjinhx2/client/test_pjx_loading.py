"""Loading indicators: which regions light on htmx:beforeRequest, and why."""

from __future__ import annotations

# htmx is never loaded in these tests; the runtime only listens for the events,
# so a hand-dispatched CustomEvent with a fake xhr exercises the real code path.
FIRE = """
(arg) => {
  const elt = document.querySelector(arg.trigger);
  const xhr = { handlers: [], addEventListener(t, fn) { this.handlers.push([t, fn]); },
                loadend() { this.handlers.forEach(([t, fn]) => t === 'loadend' && fn()); } };
  window.__xhrs = window.__xhrs || {};
  window.__xhrs[arg.name] = xhr;
  const evt = new CustomEvent('htmx:beforeRequest',
    { bubbles: true, cancelable: true, detail: { elt: elt, xhr: xhr } });
  if (arg.cancel) { evt.preventDefault(); }
  elt.dispatchEvent(evt);
}
"""

CLASSES = "(sel) => [...document.querySelectorAll(sel)].map(el => el.className)"


def fire(page, trigger, name="a", cancel=False):
    page.evaluate(FIRE, {"trigger": trigger, "name": name, "cancel": cancel})


def classes(page, selector):
    return page.evaluate(CLASSES, selector)


def test_beforerequest_lights_a_region_reacting_to_the_dirtied_keys(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="t" data-pjx-reacts="count" data-pjx-loading="skeleton">'
        '<button id="btn"></button></div>'
    )
    fire(page, "#btn")
    assert classes(page, '[data-pjx-id="t"]') == ["pjx-loading--skeleton"]


def test_beforerequest_leaves_regions_reacting_to_other_keys_dark(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="t" data-pjx-reacts="count"><button id="btn"></button></div>'
        '<div data-pjx-id="o" data-pjx-reacts="name" data-pjx-loading="skeleton"></div>'
    )
    fire(page, "#btn")
    assert classes(page, '[data-pjx-id="o"]') == [""]


def test_keyed_regions_light_only_the_instance_matching_the_trigger_load(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="t" data-pjx-reacts="rows" data-pjx-load="7">'
        '<button id="btn"></button></div>'
        '<div data-pjx-id="r7" data-pjx-reacts="rows" data-pjx-load="7" data-pjx-loading="skeleton"></div>'
        '<div data-pjx-id="r8" data-pjx-reacts="rows" data-pjx-load="8" data-pjx-loading="skeleton"></div>'
    )
    fire(page, "#btn")
    assert classes(page, '[data-pjx-id="r7"]') == ["pjx-loading--skeleton"]
    assert classes(page, '[data-pjx-id="r8"]') == [""]


def test_nested_reactive_region_targets_are_not_owned_by_the_parent(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="p" data-pjx-reacts="count"><button id="btn"></button>'
        '<span id="own" data-pjx-loading="skeleton"></span>'
        '<div data-pjx-id="c" data-pjx-reacts="other">'
        '<span id="inner" data-pjx-loading="skeleton"></span></div></div>'
    )
    fire(page, "#btn")
    assert classes(page, "#own") == ["pjx-loading--skeleton"]
    assert classes(page, "#inner") == [""]


def test_loading_extra_selector_lights_regions_that_do_not_react(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="t" data-pjx-reacts="count" data-pjx-loading-extra=".row">'
        '<button id="btn"></button></div>'
        '<div class="row" data-pjx-id="r1" data-pjx-reacts="name" data-pjx-loading="spinner"></div>'
    )
    fire(page, "#btn")
    assert classes(page, ".row") == ["row pjx-loading--spinner"]


END_EVENTS = [
    "htmx:afterOnLoad",
    "htmx:responseError",
    "htmx:timeout",
    "htmx:sendError",
    "htmx:abort",
]

END = """
(arg) => {
  const xhr = window.__xhrs[arg.name];
  document.body.dispatchEvent(new CustomEvent(arg.event,
    { bubbles: true, detail: { xhr: xhr } }));
}
"""

BODY = (
    '<div data-pjx-id="t" data-pjx-reacts="count" data-pjx-loading="skeleton">'
    '<button id="btn"></button></div>'
)


def end(page, event, name="a"):
    page.evaluate(END, {"event": event, "name": name})


import pytest


@pytest.mark.parametrize("event", END_EVENTS)
def test_each_completion_event_strips_the_loading_class(pjx_page, event):
    page = pjx_page(BODY)
    fire(page, "#btn")
    end(page, event)
    assert classes(page, '[data-pjx-id="t"]') == [""]


def test_xhr_loadend_releases_the_region(pjx_page):
    page = pjx_page(BODY)
    fire(page, "#btn")
    page.evaluate("window.__xhrs.a.loadend()")
    assert classes(page, '[data-pjx-id="t"]') == [""]


def test_overlapping_requests_keep_the_region_lit_until_the_last_resolves(pjx_page):
    page = pjx_page(BODY)
    fire(page, "#btn", name="a")
    fire(page, "#btn", name="b")
    end(page, "htmx:afterOnLoad", name="a")
    assert classes(page, '[data-pjx-id="t"]') == ["pjx-loading--skeleton"]
    end(page, "htmx:afterOnLoad", name="b")
    assert classes(page, '[data-pjx-id="t"]') == [""]


def test_cancelled_request_neither_lights_nor_registers_a_loadend_listener(pjx_page):
    page = pjx_page(BODY)
    fire(page, "#btn", cancel=True)
    assert classes(page, '[data-pjx-id="t"]') == [""]
    assert page.evaluate("window.__xhrs.a.handlers.length") == 0


def test_duplicate_completion_events_are_a_no_op(pjx_page):
    page = pjx_page(BODY)
    fire(page, "#btn")
    end(page, "htmx:afterOnLoad")
    end(page, "htmx:afterOnLoad")
    assert classes(page, '[data-pjx-id="t"]') == [""]
    assert page.evaluate("pjx.loadingCount('t')") == 0
