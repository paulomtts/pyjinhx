"""Client tier: the pjx.js browser runtime and the Python glue that ships it."""

from __future__ import annotations

from pathlib import Path

PJX_RUNTIME_PATH = Path(__file__).parent / "pjx.js"


def read_pjx_runtime() -> str:
    """Return the pjx.js source text."""
    return PJX_RUNTIME_PATH.read_text(encoding="utf-8")
