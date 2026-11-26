from typing import Literal

from pyjinhx import BaseComponent


class Badge(BaseComponent):
    """A short label. Pages target it, so the caller always passes its id."""

    auto_id = False

    label: str
    variant: Literal["neutral", "accent", "danger"] = "neutral"

    template = r"""
    <span id="{{ id }}" class="badge badge--{{ variant }}">{{ label }}</span>
    """
