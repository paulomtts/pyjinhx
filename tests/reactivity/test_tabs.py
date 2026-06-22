"""Browser contracts for the compound PJXTabGroup."""
import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def test_initial_selection_shows_first_panel(sink_page):
    expect(sink_page.locator("#rx-tabp-one")).to_be_visible()
    expect(sink_page.locator("#rx-tabp-two")).not_to_be_visible()


def test_click_tab_switches_panel(sink_page):
    sink_page.click("#rx-tab-two")
    expect(sink_page.locator("#rx-tabp-two")).to_be_visible()
    expect(sink_page.locator("#rx-tabp-one")).not_to_be_visible()
    expect(sink_page.locator("#rx-tab-two")).to_have_attribute("aria-selected", "true")


def test_arrow_keys_move_focus_manual_activation(sink_page):
    sink_page.focus("#rx-tab-one")
    sink_page.keyboard.press("ArrowRight")
    # focus moved, but panel one is still shown (manual activation)
    assert sink_page.evaluate("document.activeElement.id") == "rx-tab-two"
    expect(sink_page.locator("#rx-tabp-one")).to_be_visible()
    sink_page.keyboard.press("Enter")  # now activate
    expect(sink_page.locator("#rx-tabp-two")).to_be_visible()


def test_close_fires_cancelable_event_and_default_removes(sink_page):
    # default: closing tab two removes it and its panel
    sink_page.click("#rx-tab-two [data-pjx-tab-close]")
    expect(sink_page.locator("#rx-tab-two")).to_have_count(0)
    expect(sink_page.locator("#rx-tabp-two")).to_have_count(0)


def test_close_can_be_vetoed(sink_page):
    sink_page.evaluate(
        "document.getElementById('rx-tabs').addEventListener('pjx:tab:close', e => e.preventDefault(), {once:true})"
    )
    sink_page.click("#rx-tab-two [data-pjx-tab-close]")
    expect(sink_page.locator("#rx-tab-two")).to_have_count(1)  # survived the veto


def test_closing_selected_tab_activates_and_focuses_neighbor(sink_page):
    sink_page.click("#rx-tab-two")  # select the closeable tab
    expect(sink_page.locator("#rx-tab-two")).to_have_attribute("aria-selected", "true")
    sink_page.click("#rx-tab-two [data-pjx-tab-close]")  # close the SELECTED tab
    expect(sink_page.locator("#rx-tab-two")).to_have_count(0)
    expect(sink_page.locator("#rx-tab-one")).to_have_attribute("aria-selected", "true")
    expect(sink_page.locator("#rx-tabp-one")).to_be_visible()
    assert sink_page.evaluate("document.activeElement && document.activeElement.id") == "rx-tab-one"


def test_delete_key_closes_closeable_tab(sink_page):
    sink_page.focus("#rx-tab-two")
    sink_page.keyboard.press("Delete")
    expect(sink_page.locator("#rx-tab-two")).to_have_count(0)


def test_delete_on_non_closeable_tab_is_noop(sink_page):
    sink_page.focus("#rx-tab-one")
    sink_page.keyboard.press("Delete")
    expect(sink_page.locator("#rx-tab-one")).to_have_count(1)  # not closeable → survives
