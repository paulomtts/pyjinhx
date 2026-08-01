"""pjx.loader: ref-counted show/hide primitives app code and L4 builtins call directly."""

from __future__ import annotations

REGION = (
    '<div data-pjx-id="t" data-pjx-reacts="count" data-pjx-loading="skeleton"></div>'
)


def html_classes(page):
    return page.evaluate("document.documentElement.className")


def region_classes(page):
    return page.evaluate("document.querySelector('[data-pjx-id=\"t\"]').className")


def test_loader_page_on_sets_the_documented_css_hook(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate("pjx.loader.page(true)")
    assert html_classes(page) == "pjx-loading--page"


def test_loader_page_ref_counts_before_clearing(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate(
        "pjx.loader.page(true); pjx.loader.page(true); pjx.loader.page(false)"
    )
    assert html_classes(page) == "pjx-loading--page"
    page.evaluate("pjx.loader.page(false)")
    assert html_classes(page) == ""


def test_loader_page_clamps_at_zero(pjx_page):
    page = pjx_page("<div></div>")
    page.evaluate("pjx.loader.page(false); pjx.loader.page(false)")
    page.evaluate("pjx.loader.page(true); pjx.loader.page(false)")
    assert html_classes(page) == ""


def test_loader_region_lights_and_clears_the_regions_targets(pjx_page):
    page = pjx_page(REGION)
    page.evaluate("pjx.loader.region('t', true)")
    assert region_classes(page) == "pjx-loading--skeleton"
    page.evaluate("pjx.loader.region('t', false)")
    assert region_classes(page) == ""


def test_loader_region_shares_the_ref_count_with_htmx_driven_loading(pjx_page):
    page = pjx_page(REGION)
    page.evaluate("pjx.loader.region('t', true); pjx.loader.region('t', true)")
    assert page.evaluate("pjx.loadingCount('t')") == 2
    page.evaluate("pjx.loader.region('t', false)")
    assert region_classes(page) == "pjx-loading--skeleton"


def test_loader_region_clamps_at_zero(pjx_page):
    page = pjx_page(REGION)
    page.evaluate("pjx.loader.region('t', false)")
    assert page.evaluate("pjx.loadingCount('t')") == 0
    assert region_classes(page) == ""


def test_loader_region_for_an_unknown_id_is_a_no_op(pjx_page):
    page = pjx_page(REGION)
    assert page.evaluate("pjx.loader.region('nope', true), 'ok'") == "ok"
    assert page.evaluate("pjx.loadingCount('nope')") == 0
