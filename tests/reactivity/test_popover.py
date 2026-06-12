"""Browser contracts for the PJXPopover compound and the PJXDropdown built on it."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def test_trigger_click_opens_panel(sink_page):
    panel = sink_page.locator("#rx-pop-a-p")
    trigger = sink_page.locator("#rx-pop-a-t")
    expect(panel).to_be_hidden()
    expect(trigger).to_have_attribute("aria-expanded", "false")

    trigger.click()
    expect(panel).to_be_visible()
    expect(panel).not_to_have_attribute("hidden", "")
    expect(trigger).to_have_attribute("aria-expanded", "true")


def test_outside_click_and_escape_close(sink_page):
    panel = sink_page.locator("#rx-pop-a-p")

    sink_page.click("#rx-pop-a-t")
    expect(panel).to_be_visible()
    sink_page.click("#page-title")
    expect(panel).to_be_hidden()

    sink_page.click("#rx-pop-a-t")
    expect(panel).to_be_visible()
    sink_page.keyboard.press("Escape")
    expect(panel).to_be_hidden()


def test_opening_b_closes_a(sink_page):
    sink_page.click("#rx-pop-a-t")
    expect(sink_page.locator("#rx-pop-a-p")).to_be_visible()

    sink_page.click("#rx-pop-b-t")
    expect(sink_page.locator("#rx-pop-b-p")).to_be_visible()
    expect(sink_page.locator("#rx-pop-a-p")).to_be_hidden()
    expect(sink_page.locator("#rx-pop-a-t")).to_have_attribute("aria-expanded", "false")


def test_data_pjx_close_inside_dropdown_closes_menu_only(sink_page):
    menu = sink_page.locator("#rx-drop-menu")
    sink_page.click("#rx-drop-trigger")
    expect(menu).to_be_visible()

    # Hold popover A open via the API (a trigger click would close the menu).
    sink_page.evaluate("pjx.popover.open('rx-pop-a-p')")
    expect(sink_page.locator("#rx-pop-a-p")).to_be_visible()

    sink_page.click("#drop-close-item")
    expect(menu).to_be_hidden()
    expect(sink_page.locator("#rx-pop-a-p")).to_be_visible()
