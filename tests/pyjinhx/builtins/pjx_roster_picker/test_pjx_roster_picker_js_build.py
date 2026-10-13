"""The single pjx_roster_picker.js asset: its picker source, its build script, and the committed output.

Every check compares file bytes or a pure function's return value, so no page is needed.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PICKER_DIR = ROOT / "pyjinhx" / "builtins" / "ui" / "pjx_roster_picker"
PICKER = PICKER_DIR / "src" / "picker.js"


def test_picker_source_is_one_guarded_iife():
    source = PICKER.read_text(encoding="utf-8")
    assert source.startswith("(function () {")
    assert source.endswith("})();\n")
    assert "window.pjx.rosterPicker" in source


def test_picker_source_is_lf_only():
    assert b"\r" not in PICKER.read_bytes()
