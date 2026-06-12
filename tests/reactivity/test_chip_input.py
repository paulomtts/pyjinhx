"""Browser contracts for PJXChipInput: chips, vetoes, and form submission."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]

FIELD = "#rx-chips .pjx-chip-input__field"
CHIPS = "#rx-chips [data-pjx-chip]"


def test_enter_adds_chip_and_drops_duplicates(sink_page):
    field = sink_page.locator(FIELD)
    field.fill("alpha")
    field.press("Enter")

    chips = sink_page.locator(CHIPS)
    expect(chips).to_have_count(1)
    expect(sink_page.locator("#rx-chips input[type=hidden]")).to_have_value("alpha")
    expect(field).to_have_value("")

    field.fill("alpha")
    field.press("Enter")
    expect(chips).to_have_count(1)  # duplicate silently dropped
    expect(field).to_have_value("")  # but the field still clears


def test_backspace_on_empty_field_removes_last_chip(sink_page):
    field = sink_page.locator(FIELD)
    for value in ("one", "two"):
        field.fill(value)
        field.press("Enter")
    expect(sink_page.locator(CHIPS)).to_have_count(2)

    field.press("Backspace")
    expect(sink_page.locator(CHIPS)).to_have_count(1)
    expect(sink_page.locator(f"{CHIPS} .pjx-chip-input__label")).to_have_text("one")


def test_before_add_veto_keeps_text(sink_page):
    sink_page.evaluate(
        "document.getElementById('rx-chips')"
        ".addEventListener('pjx:chip-input:before-add', (e) => e.preventDefault(), { once: true })"
    )
    field = sink_page.locator(FIELD)
    field.fill("vetoed")
    field.press("Enter")

    expect(sink_page.locator(CHIPS)).to_have_count(0)
    expect(field).to_have_value("vetoed")


def test_submit_commits_pending_text(sink_page):
    sink_page.locator(FIELD).fill("pending")
    with sink_page.expect_response("**/chips/echo") as response_info:
        sink_page.click("#chip-submit")
    assert response_info.value.json() == {"tags": ["pending"]}


def test_enter_on_empty_field_submits_form(sink_page):
    field = sink_page.locator(FIELD)
    field.fill("alpha")
    field.press("Enter")
    expect(sink_page.locator(CHIPS)).to_have_count(1)

    with sink_page.expect_response("**/chips/echo") as response_info:
        field.press("Enter")  # empty field: Enter falls through to the form
    assert response_info.value.json() == {"tags": ["alpha"]}
