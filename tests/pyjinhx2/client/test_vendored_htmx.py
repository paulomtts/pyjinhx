"""The vendored htmx asset ships with client/ and reads back double-load guarded."""

from __future__ import annotations

from pyjinhx2.client import HTMX_RUNTIME_PATH, read_vendored_htmx


def test_runtime_path_points_at_vendored_htmx():
    assert HTMX_RUNTIME_PATH.name == "htmx.min.js"
    assert HTMX_RUNTIME_PATH.parent.name == "client"
    assert HTMX_RUNTIME_PATH.is_file()


def test_returns_vendored_htmx_library_source():
    source = read_vendored_htmx()
    # the vendored htmx library defines the global
    assert "var htmx" in source


def test_guarded_against_double_load():
    # If the page already loaded htmx (e.g. the app added it itself), our
    # inlined copy must no-op rather than redefine it.
    source = read_vendored_htmx()
    assert source.startswith("if (!window.htmx) {\n")
    assert source.endswith("\n}\n")


def test_repeated_reads_are_identical():
    assert read_vendored_htmx() == read_vendored_htmx()


def test_asset_records_the_pinned_version():
    # Read the raw file, pre-guard-wrap: the header names the pin so a stale
    # vendored copy is obvious in a diff.
    raw = HTMX_RUNTIME_PATH.read_text(encoding="utf-8")
    first_line = raw.split("\n", 1)[0]
    assert first_line == "/* htmx 2.0.3 — vendored by scripts/vendor_htmx2.py (0BSD) */"
