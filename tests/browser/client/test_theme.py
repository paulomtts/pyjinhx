"""The opt-in theme sheet: one server-emitted <style id="pjx-theme"> per cold render."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pyjinhx.client.inject import inject_runtime
from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx.rendering.assets import emit_assets
from pyjinhx.rendering.session import RenderSession


@pytest.fixture
def themed() -> Iterator[None]:
    configure_pyjinhx(PjxSettings(theme="default"))
    # Teardown after yield runs even when the test fails, so the theme never
    # leaks into a later test that expects the default settings.
    yield
    shutdown_pyjinhx()


def test_theme_applies_in_chromium_and_data_pjx_theme_dark_flips_it(themed, page):
    session = RenderSession()
    inject_runtime(session)
    page.emulate_media(color_scheme="light")
    page.set_content(
        f"<html><head>{emit_assets(session)}</head><body>"
        '<div data-pjx-theme="dark" id="w"><span id="i"></span></div>'
        "</body></html>"
    )
    root = page.evaluate(
        "getComputedStyle(document.documentElement)"
        ".getPropertyValue('--pjx-color-surface').trim()"
    )
    inner = page.evaluate(
        "getComputedStyle(document.getElementById('i'))"
        ".getPropertyValue('--pjx-color-surface').trim()"
    )
    assert root == "#ffffff"
    assert inner == "#18181b"
