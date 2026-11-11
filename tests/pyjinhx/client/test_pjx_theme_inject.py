"""The opt-in theme sheet: one server-emitted <style id="pjx-theme"> per cold render."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import pyjinhx
from pyjinhx.assets import AssetMode, emit_assets
from pyjinhx.client import read_pjx_theme_css
from pyjinhx.client.inject import PJX_MOUNTED_HEADER, inject_runtime
from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx.session import RenderSession

THEME_TAG = f'<style id="pjx-theme">{read_pjx_theme_css()}</style>'


class FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


BUILTIN_CSS = Path(pyjinhx.__file__).parent / "builtins" / "pjx_table" / "pjx_table.css"


def _themed_session_with_css(tmp_path: Path) -> RenderSession:
    """A cold-injected session holding one builtin and one app stylesheet."""
    app_css = tmp_path / "app.css"
    app_css.write_text(".app { color: red; }")
    session = RenderSession()
    session.css_assets.update({BUILTIN_CSS, app_css})
    inject_runtime(session)
    return session


def _stub_resolver(path: Path) -> str:
    return f"/static/{path.name}"


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


def test_a_second_inject_does_not_duplicate_the_theme(themed):
    session = RenderSession()
    inject_runtime(session)
    inject_runtime(session)
    assert emit_assets(session).count('<style id="pjx-theme">') == 1


def test_inline_css_order_is_theme_then_pjx_style_then_builtin_then_app(
    themed, tmp_path
):
    out = emit_assets(_themed_session_with_css(tmp_path))
    assert out.startswith(THEME_TAG)
    assert out.count(THEME_TAG) == 1
    theme_at = out.index('<style id="pjx-theme">')
    style_at = out.index('<style id="pjx-style">')
    first_asset_at = out.index('<style data-pjx-asset="')
    app_at = out.index(".app { color: red; }")
    assert theme_at < style_at < first_asset_at < app_at
    # Only the two component stylesheets are tokened: the theme block is a
    # runtime block like pjx-style, so pjx.js never relocates or reports it.
    assert out.count('<style data-pjx-asset="') == 2
    assert "data-pjx-asset" not in THEME_TAG


def test_link_css_order_puts_the_theme_before_every_stylesheet_link(themed, tmp_path):
    session = _themed_session_with_css(tmp_path)
    session.css_mode = AssetMode.LINK
    out = emit_assets(session, resolver=_stub_resolver)
    assert out.startswith(THEME_TAG)
    assert out.count(THEME_TAG) == 1
    assert (
        out.index('<style id="pjx-theme">')
        < out.index('<style id="pjx-style">')
        < out.index('<link rel="stylesheet"')
    )


def test_theme_is_emitted_even_when_css_mode_is_none(themed, tmp_path):
    session = _themed_session_with_css(tmp_path)
    session.css_mode = AssetMode.NONE
    out = emit_assets(session)
    assert out.startswith(THEME_TAG)
    assert out.count(THEME_TAG) == 1


# Kept after every themed test on purpose: if a fixture ever stopped restoring
# the settings, this is the test that would see the leaked theme.
def test_theme_off_by_default_leaves_theme_style_unset():
    session = RenderSession()
    inject_runtime(session)
    assert session.theme_style is None
    out = emit_assets(session)
    assert "pjx-theme" not in out
    assert out == f"{session.runtime_style}\n{session.runtime_script}"
