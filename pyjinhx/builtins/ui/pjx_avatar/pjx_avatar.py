from pydantic import Field, computed_field, field_validator

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs

_NAMED_SIZES = {"sm", "md", "lg"}


class PJXAvatar(BaseComponent):
    src: str = ""
    alt: str = ""
    initials: str = ""
    # Named tokens ("sm", "md", "lg") emit a BEM modifier class.
    # An int (px) or any other CSS length string (e.g. "36px", "2.5rem")
    # renders inline width/height instead and omits the modifier class.
    size: str | int = "md"
    class_name: AttrValue = ""
    color: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @field_validator("initials", mode="before")
    @classmethod
    def cap_initials(cls, value: str) -> str:
        if not value:
            return ""
        text = str(value).strip()
        return text[:2] if len(text) > 2 else text

    @computed_field
    @property
    def size_is_token(self) -> bool:
        return str(self.size) in _NAMED_SIZES

    @computed_field
    @property
    def size_css(self) -> str:
        """CSS length string for inline style when size is not a named token."""
        val = self.size
        if isinstance(val, int):
            return f"{val}px"
        return str(val)
