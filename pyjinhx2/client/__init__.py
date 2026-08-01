"""Client tier: the pjx.js browser runtime and the Python glue that ships it."""

from __future__ import annotations

from pathlib import Path

PJX_RUNTIME_PATH = Path(__file__).parent / "pjx.js"


def read_pjx_runtime() -> str:
    """Return the pjx.js source text."""
    return PJX_RUNTIME_PATH.read_text(encoding="utf-8")


HTMX_RUNTIME_PATH = Path(__file__).parent / "htmx.min.js"


def read_vendored_htmx() -> str:
    """Return the vendored htmx source, guarded so it no-ops if htmx is present.

    pjx.js depends on htmx, so we ship and inline a pinned copy of it. The
    ``if (!window.htmx)`` guard means a page that already loaded its own htmx
    keeps that copy instead of redefining it — inlining ours is safe either way.
    """
    source = HTMX_RUNTIME_PATH.read_text(encoding="utf-8")
    return f"if (!window.htmx) {{\n{source}\n}}\n"
