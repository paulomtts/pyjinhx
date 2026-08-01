"""Without htmx, reactivity silently does nothing — pjx.js must say so, not throw."""

from __future__ import annotations

from playwright.sync_api import Page

from pyjinhx2.client import read_pjx_runtime


def test_missing_htmx_logs_a_console_error(page: Page):
    errors = []
    page.on(
        "console", lambda msg: errors.append(msg.text) if msg.type == "error" else None
    )
    page.set_content("<body><div></div></body>")
    page.add_script_tag(content=read_pjx_runtime())
    assert any("htmx" in text for text in errors)


def test_runtime_still_loads_and_scans_without_htmx(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1"></div>',
        with_htmx=False,
    )
    assert page.evaluate("pjx.manifest()") == [
        {"id": "a1", "type": "Card", "hash": "h1"}
    ]


def test_no_console_error_when_htmx_is_present(page: Page):
    errors = []
    page.on(
        "console", lambda msg: errors.append(msg.text) if msg.type == "error" else None
    )
    page.set_content("<body><div></div></body>")
    page.evaluate("window.htmx = {}")
    page.add_script_tag(content=read_pjx_runtime())
    assert errors == []


def test_loading_and_toast_apis_exist_without_htmx(pjx_page):
    page = pjx_page("<div></div>", with_htmx=False)
    assert page.evaluate("typeof pjx.toast") == "function"
    assert page.evaluate("typeof pjx.loader.page") == "function"
    assert page.evaluate("typeof pjx.loader.region") == "function"


def test_style_is_injected_even_without_htmx(pjx_page):
    page = pjx_page("<div></div>", with_htmx=False)
    assert page.evaluate("document.querySelectorAll('#pjx-style').length") == 1


def test_loader_and_toast_do_not_throw_without_htmx(pjx_page):
    page = pjx_page("<div></div>", with_htmx=False)
    assert (
        page.evaluate(
            "pjx.toast({message: 'x'}), pjx.loader.page(true), pjx.loader.page(false), 'ok'"
        )
        == "ok"
    )
