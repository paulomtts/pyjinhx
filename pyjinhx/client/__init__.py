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


# loading_indicator and page_loader live here rather than under builtins/ui/:
# they have no host element, no .pjx template and no per-request descriptor
# to gate delivery on, so the L4 lazy-asset door doesn't apply — they ship
# unconditionally with every cold render of the runtime.
LOADING_INDICATOR_JS_PATH = Path(__file__).parent / "loading_indicator.js"
LOADING_INDICATOR_CSS_PATH = Path(__file__).parent / "loading_indicator.css"
PAGE_LOADER_JS_PATH = Path(__file__).parent / "page_loader.js"
PAGE_LOADER_CSS_PATH = Path(__file__).parent / "page_loader.css"


def read_loading_indicator_js() -> str:
    """Return the loading-indicator artifact's source text."""
    return LOADING_INDICATOR_JS_PATH.read_text(encoding="utf-8")


def read_page_loader_js() -> str:
    """Return the page-loader artifact's source text."""
    return PAGE_LOADER_JS_PATH.read_text(encoding="utf-8")


def read_pjx_style_css() -> str:
    """Return the always-on runtime CSS: loading-indicator then page-loader."""
    return (
        LOADING_INDICATOR_CSS_PATH.read_text(encoding="utf-8")
        + PAGE_LOADER_CSS_PATH.read_text(encoding="utf-8")
    )
