"""Browser contracts for PJXModal (and the sibling PJXDrawer dialog)."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def test_open_and_close_via_data_attributes(sink_page):
    modal = sink_page.locator("#rx-modal")
    expect(modal).not_to_be_visible()

    sink_page.click("#modal-open-btn")
    expect(modal).to_be_visible()
    expect(modal).to_have_attribute("open", "")

    sink_page.click("#rx-modal [data-pjx-close]")
    expect(modal).not_to_be_visible()


def test_before_close_veto_blocks_escape_once(sink_page):
    sink_page.click("#modal-open-btn")
    modal = sink_page.locator("#rx-modal")
    expect(modal).to_be_visible()

    sink_page.evaluate(
        "document.addEventListener('pjx:modal:before-close', (e) => e.preventDefault(), { once: true })"
    )
    sink_page.keyboard.press("Escape")
    sink_page.wait_for_timeout(400)
    expect(modal).to_be_visible()

    sink_page.keyboard.press("Escape")
    expect(modal).not_to_be_visible()


def test_api_round_trip_returns_booleans(sink_page):
    assert sink_page.evaluate("pjx.modal.open('rx-modal')") is True
    assert sink_page.evaluate("pjx.modal.open('rx-modal')") is False  # already open

    # First close starts the closing animation; a second close mid-flight is refused.
    assert sink_page.evaluate("[pjx.modal.close('rx-modal'), pjx.modal.close('rx-modal')]") == [True, False]
    expect(sink_page.locator("#rx-modal")).not_to_be_visible()
    assert sink_page.evaluate("pjx.modal.close('rx-modal')") is False  # already closed


def test_remove_on_close_defers_removal_until_request_settles(sink_page):
    """A submit that both fires an htmx request and closes a remove_on_close
    modal must still deliver the response: HX-Trigger events dispatch on the
    requesting element, so the dialog defers its removal until the in-flight
    request settles (a detached requester's events can't bubble to window).
    Regression test for the slow-response race — on the old immediate-removal
    behavior the toast below never arrives."""
    sink_page.click("#remove-modal-open-btn")
    modal = sink_page.locator("#rx-remove-modal")
    expect(modal).to_be_visible()

    sink_page.click("#rx-remove-submit")
    toast = sink_page.locator("#rx-toasts .pjx-toast")
    expect(toast.locator(".pjx-toast__message")).to_have_text("Slow saved!", timeout=5000)
    # And the dialog still honors remove_on_close once the request settles.
    expect(sink_page.locator("#rx-remove-modal")).to_have_count(0)


def test_drawer_opens_and_closes_via_data_attributes(sink_page):
    drawer = sink_page.locator("#rx-drawer")
    expect(drawer).not_to_be_visible()

    sink_page.click("#drawer-open-btn")
    expect(drawer).to_be_visible()

    sink_page.click("#rx-drawer [data-pjx-close]")
    expect(drawer).not_to_be_visible()
