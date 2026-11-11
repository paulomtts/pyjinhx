"""The opt-in theme sheet: one server-emitted <style id="pjx-theme"> per cold render."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pyjinhx.assets import AssetMode, emit_assets
from pyjinhx.client import read_pjx_theme_css
from pyjinhx.client.inject import PJX_MOUNTED_HEADER, inject_runtime
from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx.session import RenderSession

THEME_TAG = f'<style id="pjx-theme">{read_pjx_theme_css()}</style>'


class FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


@pytest.fixture
def themed() -> Iterator[None]:
    configure_pyjinhx(PjxSettings(theme="default"))
    # Teardown after yield runs even when the test fails, so the theme never
    # leaks into a later test that expects the default settings.
    yield
    shutdown_pyjinhx()


def test_theme_on_records_the_exact_theme_tag(themed):
    session = RenderSession()
    inject_runtime(session)
    assert session.theme_style == THEME_TAG


@pytest.mark.parametrize(
    "request_",
    ['["btn-1"]', FakeRequest({PJX_MOUNTED_HEADER: "[]"})],
    ids=["mounted-string", "mounted-headers"],
)
def test_mounted_request_never_records_the_theme(themed, request_):
    session = RenderSession()
    inject_runtime(session, request_)
    assert session.theme_style is None
    assert "pjx-theme" not in emit_assets(session)


def test_theme_is_not_recorded_when_js_is_not_inline(themed):
    session = RenderSession()
    session.js_mode = AssetMode.NONE
    inject_runtime(session)
    assert session.theme_style is None


def test_the_setting_is_read_when_inject_runs_not_at_import():
    before = RenderSession()
    inject_runtime(before)
    assert before.theme_style is None

    configure_pyjinhx(PjxSettings(theme="default"))
    try:
        after = RenderSession()
        inject_runtime(after)
        assert after.theme_style == THEME_TAG
    finally:
        shutdown_pyjinhx()


# Kept after every themed test on purpose: if a fixture ever stopped restoring
# the settings, this is the test that would see the leaked theme.
def test_theme_off_by_default_leaves_theme_style_unset():
    session = RenderSession()
    inject_runtime(session)
    assert session.theme_style is None
    out = emit_assets(session)
    assert "pjx-theme" not in out
    assert out == f"{session.runtime_style}\n{session.runtime_script}"
