"""Browser contracts for the PJXPasswordInput visibility toggle."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def test_toggle_reveals_and_hides_password(sink_page):
    field = sink_page.locator("#rx-pw-field")
    toggle = sink_page.locator("#rx-pw [data-pjx-password-toggle]")

    field.fill("hunter2")
    expect(field).to_have_attribute("type", "password")
    expect(toggle).to_have_attribute("aria-pressed", "false")

    toggle.click()
    expect(field).to_have_attribute("type", "text")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(toggle).to_contain_class("pjx-password-input__toggle--on")

    toggle.click()
    expect(field).to_have_attribute("type", "password")
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(toggle).not_to_contain_class("pjx-password-input__toggle--on")
