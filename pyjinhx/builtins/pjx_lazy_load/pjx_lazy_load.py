from typing import Literal

from pydantic import Field

from pyjinhx.component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXLazyLoad(BaseComponent):
    """A placeholder that fetches its own replacement over HTMX when triggered.

    Also serves as an infinite-scroll sentinel: the server re-emits one as the
    last row or list item of each page, carrying the next cursor in ``url``.
    """

    url: str
    when: Literal["viewport", "reveal", "load"] = "viewport"
    trigger: str = ""
    swap: str = "outerHTML"
    tag: Literal["div", "li", "tr"] = "div"
    content: Slot = ""
    error: Slot = ""
    error_text: str = "Failed to load."
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
