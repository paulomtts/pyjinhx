from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXToggleSwitch(BaseComponent):
    """A checkbox rendered as a sliding on/off switch.

    The visually-hidden checkbox carries ``name``/``value`` and the
    ``checked``/``disabled`` state; the track and thumb spans are the visible
    control, and ``label``, when set, renders as trailing text inside the same
    clickable ``<label>`` root.
    """

    name: str = ""
    value: str = "on"
    checked: bool = False
    label: str = ""
    disabled: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
