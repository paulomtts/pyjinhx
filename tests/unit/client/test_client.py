"""The client/ package exists and exposes its runtime source to Python."""

from __future__ import annotations

from pyjinhx.client import PJX_RUNTIME_PATH, read_pjx_runtime


def test_runtime_path_points_at_pjx_js():
    assert PJX_RUNTIME_PATH.name == "pjx.js"
    assert PJX_RUNTIME_PATH.is_file()


def test_read_pjx_runtime_returns_source():
    source = read_pjx_runtime()
    assert "window.pjx" in source
    assert "htmx:configRequest" in source
