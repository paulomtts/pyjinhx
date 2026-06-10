"""Browser contracts for Panel/PanelTrigger reveal events, LazyPanel(when="reveal"),
and TabGroup panel switching."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def test_trigger_reveals_panel_exactly_once(sink_page):
    sink_page.evaluate(
        """
        window.__revealsB = 0;
        document.getElementById('rx-panel-panel-b')
            .addEventListener('px:reveal', () => window.__revealsB++);
        """
    )

    sink_page.click("#trig-b-btn")
    panel_b = sink_page.locator("#rx-panel-panel-b")
    expect(panel_b).to_be_visible()
    expect(panel_b).to_have_attribute("data-px-revealed", "")
    expect(sink_page.locator("#rx-panel-panel-a")).to_be_hidden()
    assert sink_page.evaluate("window.__revealsB") == 1

    sink_page.click("#trig-b-btn")  # already active: nothing to announce
    sink_page.wait_for_timeout(200)
    assert sink_page.evaluate("window.__revealsB") == 1


def test_lazy_panel_loads_on_first_reveal(sink_page):
    expect(sink_page.locator("#lazy-placeholder")).to_have_count(1)
    expect(sink_page.locator("#rx-lazy-loaded")).to_have_count(0)

    sink_page.click("#trig-b-btn")
    expect(sink_page.locator("#rx-lazy-loaded")).to_be_visible()
    expect(sink_page.locator("#lazy-placeholder")).to_have_count(0)


def test_tab_group_switch_reveals_panel(sink_page):
    second_tab = sink_page.locator("#rx-tabs-tab-1")
    second_panel = sink_page.locator("#rx-tabs-panel-1")
    expect(second_panel).to_be_hidden()

    second_tab.click()
    expect(second_panel).to_be_visible()
    expect(second_panel).to_have_attribute("data-px-revealed", "")
    expect(second_tab).to_have_attribute("aria-selected", "true")
    expect(sink_page.locator("#rx-tabs-tab-0")).to_have_attribute("aria-selected", "false")
    expect(sink_page.locator("#rx-tabs-panel-0")).to_be_hidden()
