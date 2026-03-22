from __future__ import annotations

from pyjinhx import BaseComponent
from typing import Optional, Union


class UnifiedComponent(BaseComponent):
    id: str
    text: Optional[str] = None
    title: Optional[str] = None
    nested: Optional[UnifiedComponent] = None
    items: Optional[list[Union[UnifiedComponent, str]]] = None
    sections: Optional[dict[str, Union[UnifiedComponent, str]]] = None
