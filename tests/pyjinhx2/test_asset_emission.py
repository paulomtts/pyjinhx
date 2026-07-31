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


import pytest

from pyjinhx2.assets import emit_assets


def _session(tmp_path: Path) -> RenderSession:
    return RenderSession(template_dir=str(tmp_path))


def test_inline_emits_style_and_script_with_exact_file_contents(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    session = _session(tmp_path)
    session.css_assets.add(css)
    session.js_assets.add(js)

    out = emit_assets(session)

    assert "<style>.box { color: red; }</style>" in out
    assert "<script>console.log('box');</script>" in out


def test_none_mode_emits_nothing_for_that_kind(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    session = _session(tmp_path)
    session.css_assets.add(css)
    session.js_assets.add(js)
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE

    assert emit_assets(session) == ""


def test_mixed_modes_emit_css_only(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    session = _session(tmp_path)
    session.css_assets.add(css)
    session.js_assets.add(js)
    session.js_mode = AssetMode.NONE

    out = emit_assets(session)

    assert "<style>" in out
    assert "<script>" not in out


def test_emission_order_is_sorted_by_path_and_stable(tmp_path):
    for name, body in (("z.css", ".z {}"), ("a.css", ".a {}"), ("m.css", ".m {}")):
        (tmp_path / name).write_text(body)
    session = _session(tmp_path)
    session.css_assets.update(
        {tmp_path / "z.css", tmp_path / "a.css", tmp_path / "m.css"}
    )

    first = emit_assets(session)

    assert first.index(".a {}") < first.index(".m {}") < first.index(".z {}")
    assert emit_assets(session) == first


def test_missing_asset_file_raises(tmp_path):
    session = _session(tmp_path)
    session.css_assets.add(tmp_path / "gone.css")

    with pytest.raises(OSError):
        emit_assets(session)


def test_no_assets_emits_empty_string(tmp_path):
    assert emit_assets(_session(tmp_path)) == ""
