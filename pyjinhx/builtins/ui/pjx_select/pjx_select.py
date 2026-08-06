from typing import ClassVar, Self

from pydantic import BaseModel, model_validator

from pyjinhx._component import AttrValue, BaseComponent


class SelectOption(BaseModel):
    """One entry in a PJXSelect option list: the posted value and its visible label."""

    value: str
    label: str


class PJXSelect(BaseComponent):
    """A select styled to replace a bare ``<select>``, single-choice or multi.

    The JS finds trigger and panel through ``data-pjx-select``, mirroring
    pjx_popover's trigger/panel split. A hidden native ``<select>`` carries the
    same options so a plain form submit still posts a value without JS. A
    ``value`` that matches no option renders unselected rather than raising.

    With ``multiple``, ``value`` is a list, every option row gets a checkbox,
    and the trigger summarises two or more selections as chips.

    Panels holding strictly more than ``_FILTER_THRESHOLD`` options open with a
    search input above the list; shorter lists render without one. The input is
    UI-only — it hides option buttons in the browser and never posts.
    """

    # Below this many options a filter adds more chrome than it saves, so the
    # input is omitted from the markup entirely rather than rendered hidden.
    _FILTER_THRESHOLD: ClassVar[int] = 8

    name: str
    options: list[SelectOption]
    value: str | list[str] | None = None
    multiple: bool = False
    placeholder: str = "Select…"
    disabled: bool = False
    class_name: AttrValue = ""

    @model_validator(mode="after")
    def _check_value_shape(self) -> Self:
        # An unknown value is tolerated (renders unselected), but the wrong
        # *shape* is a caller bug that would silently drop the selection.
        if self.value is None:
            return self
        if self.multiple and not isinstance(self.value, list):
            raise ValueError("value must be a list when multiple=True")
        if not self.multiple and not isinstance(self.value, str):
            raise ValueError("value must be a str when multiple=False")
        return self
