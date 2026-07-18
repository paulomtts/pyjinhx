"""Browser contracts for PJXAccordionTrigger's disabled state."""
import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def test_disabled_trigger_enter_key_does_not_open(sink_page):
    sink_page.focus("#rx-accordion-trigger-disabled")
    sink_page.keyboard.press("Enter")
    expect(sink_page.locator("#rx-accordion-disabled")).not_to_have_js_property("open", True)


def test_enabled_trigger_click_opens(sink_page):
    sink_page.click("#rx-accordion-trigger-open")
    expect(sink_page.locator("#rx-accordion-open")).to_have_js_property("open", True)
