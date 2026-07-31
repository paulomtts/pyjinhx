"""L2.2.2: INLINE/NONE emission of accumulated assets at the top-level serialize."""

from pathlib import Path

from pyjinhx2.assets import AssetMode
from pyjinhx2.session import RenderSession


def test_asset_mode_has_exactly_inline_and_none():
    assert AssetMode.INLINE.value == "inline"
    assert AssetMode.NONE.value == "none"
    assert set(AssetMode) == {AssetMode.INLINE, AssetMode.NONE}


def test_session_defaults_both_kinds_to_inline():
    session = RenderSession(template_dir=str(Path("tests/templates")))
    assert session.css_mode is AssetMode.INLINE
    assert session.js_mode is AssetMode.INLINE
