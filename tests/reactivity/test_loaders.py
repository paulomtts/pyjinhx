"""Browser contracts for RegionLoader (ref-counting, resurrect, reduced motion)
and PageLoader (htmx navigation tracking)."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]

REGION = "#rx-region"


def test_region_show_is_reference_counted(sink_page):
    sink_page.evaluate("px.loader.region.show('rx-region'); px.loader.region.show('rx-region')")
    region = sink_page.locator(REGION)
    expect(region).to_contain_class("px-region-loader--visible")

    sink_page.evaluate("px.loader.region.hide('rx-region')")
    sink_page.wait_for_timeout(400)  # outlive the 250ms hide fallback
    expect(region).to_contain_class("px-region-loader--visible")  # one source still active

    sink_page.evaluate("px.loader.region.hide('rx-region')")
    expect(region).not_to_contain_class("px-region-loader--visible", timeout=2000)


def test_resurrecting_show_fires_one_show_event(sink_page):
    sink_page.evaluate(
        """
        window.__rlShows = 0;
        document.getElementById('rx-region')
            .addEventListener('px:region-loader:show', () => window.__rlShows++);
        px.loader.region.show('rx-region');
        px.loader.region.hide('rx-region');
        px.loader.region.show('rx-region');
        """
    )
    sink_page.wait_for_timeout(600)  # past the hide fallback: any stale finalize would have run
    assert sink_page.evaluate("window.__rlShows") == 1
    expect(sink_page.locator(REGION)).to_contain_class("px-region-loader--visible")


def test_reduced_motion_hide_uses_timer_fallback(browser, server_url):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    try:
        page.goto(f"{server_url}/")
        page.evaluate("px.loader.region.show('rx-region')")
        expect(page.locator(REGION)).to_contain_class("px-region-loader--visible")

        page.evaluate("px.loader.region.hide('rx-region')")
        page.wait_for_timeout(500)  # no animationend here; the 250ms fallback must finalize
        assert "px-region-loader--visible" not in page.locator(REGION).get_attribute("class")
    finally:
        context.close()


def test_page_loader_tracks_htmx_navigation(sink_page):
    loader = sink_page.locator("#rx-page-loader")
    expect(loader).not_to_contain_class("px-page-loader--active")

    sink_page.click("#nav-btn")
    expect(loader).to_contain_class("px-page-loader--active")  # in flight (endpoint sleeps 0.3s)

    expect(sink_page.locator("#slow-loaded")).to_be_visible()
    expect(loader).not_to_contain_class("px-page-loader--active", timeout=2000)
