from pydantic import BaseModel

from pyjinhx._component import AttrValue, BaseComponent


class SelectOption(BaseModel):
    """One entry in a PJXSelect option list: the posted value and its visible label."""

    value: str
    label: str


class PJXSelect(BaseComponent):
    """A single-choice select styled to replace a bare ``<select>``.

    The JS finds trigger and panel through ``data-pjx-select``, mirroring
    pjx_popover's trigger/panel split. A hidden native ``<select>`` carries the
    same options so a plain form submit still posts a value without JS. A
    ``value`` that matches no option renders unselected rather than raising.
    """

    name: str
    options: list[SelectOption]
    value: str | None = None
    placeholder: str = "Select…"
    disabled: bool = False
    class_name: AttrValue = ""
