"""Browser contracts for Notification (autoshow + API) and the ToastHost."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def test_htmx_fragment_autoshows_then_times_out(sink_page):
    sink_page.click("#note-frag-btn")

    fragment = sink_page.locator("#rx-note-frag")
    expect(fragment).to_contain_class("px-notification--visible")
    expect(fragment).to_contain_text("Fragment note")

    # data-timeout is 600ms; the hide animation finalizes shortly after.
    expect(fragment).not_to_contain_class("px-notification--visible", timeout=3000)


def test_api_show_and_hide(sink_page):
    note = sink_page.locator("#rx-note")
    assert sink_page.evaluate("px.notification.show('rx-note')") is True
    expect(note).to_contain_class("px-notification--visible")
    assert sink_page.evaluate("px.notification.show('rx-note')") is False  # already visible

    assert sink_page.evaluate("px.notification.hide('rx-note')") is True
    expect(note).not_to_contain_class("px-notification--visible")


def test_hx_trigger_header_shows_toast_and_dismiss_removes_it(sink_page):
    sink_page.click("#save-btn")

    toast = sink_page.locator("#rx-toasts .px-toast")
    expect(toast).to_have_count(1)
    expect(toast).to_contain_class("px-toast--success")
    expect(toast.locator(".px-toast__message")).to_have_text("Saved!")

    toast.locator(".px-toast__dismiss").click()
    expect(sink_page.locator("#rx-toasts .px-toast")).to_have_count(0)
