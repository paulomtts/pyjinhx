from __future__ import annotations

from pyjinhx_v0 import BaseComponent


class UnifiedComponent(BaseComponent):
    text: str | None = None
    title: str | None = None
    nested: UnifiedComponent | None = None
    items: list[UnifiedComponent | str] | None = None
    sections: dict[str, UnifiedComponent | str] | None = None
