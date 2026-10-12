"""The single pjx_graph.js asset: its engine source, its build script, and the committed output."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GRAPH_DIR = ROOT / "pyjinhx" / "builtins" / "ui" / "pjx_graph"
ENGINE = GRAPH_DIR / "src" / "engine.js"


def test_engine_source_is_one_guarded_iife():
    source = ENGINE.read_text(encoding="utf-8")
    assert source.startswith("(function () {")
    assert source.endswith("})();\n")
    assert "window.pjx.graph" in source


def test_engine_source_is_lf_only():
    assert b"\r" not in ENGINE.read_bytes()
