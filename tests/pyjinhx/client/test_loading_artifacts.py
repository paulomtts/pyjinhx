"""The loading-indicator / page-loader artifacts, driven by core's events."""

from __future__ import annotations

REGION = (
    '<div data-pjx-id="t" data-pjx-reacts="count" data-pjx-loading="skeleton"></div>'
)


def fire(page, name, detail="{}"):
    page.evaluate(
        f"document.dispatchEvent(new CustomEvent('{name}', {{detail: {detail}}}))"
    )


def test_region_start_applies_the_variant_class(pjx_full_page):
    page = pjx_full_page(REGION)
    fire(page, "pjx:region-loading-start", "{id: 't'}")
    assert page.evaluate(
        "document.querySelector('[data-pjx-id=\"t\"]').className"
    ) == "pjx-loading--skeleton"


def test_region_end_removes_the_class(pjx_full_page):
    page = pjx_full_page(REGION)
    fire(page, "pjx:region-loading-start", "{id: 't'}")
    fire(page, "pjx:region-loading-end", "{id: 't'}")
    assert page.evaluate("document.querySelector('[data-pjx-id=\"t\"]').className") == ""


def test_region_events_for_an_unknown_id_are_a_no_op(pjx_full_page):
    page = pjx_full_page(REGION)
    fire(page, "pjx:region-loading-start", "{id: 'nope'}")
    assert page.evaluate("document.querySelector('[data-pjx-id=\"t\"]').className") == ""


def test_spinner_variant_is_honoured(pjx_full_page):
    page = pjx_full_page(
        '<div data-pjx-id="s" data-pjx-reacts="c" data-pjx-loading="spinner"></div>'
    )
    fire(page, "pjx:region-loading-start", "{id: 's'}")
    assert page.evaluate(
        "document.querySelector('[data-pjx-id=\"s\"]').className"
    ) == "pjx-loading--spinner"


def test_page_events_toggle_the_documented_hook(pjx_full_page):
    page = pjx_full_page("<div></div>")
    fire(page, "pjx:page-loading-start")
    assert page.evaluate("document.documentElement.className") == "pjx-loading--page"
    fire(page, "pjx:page-loading-end")
    assert page.evaluate("document.documentElement.className") == ""
