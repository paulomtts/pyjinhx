from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXChipInput(BaseComponent):
    """A multi-value text field that renders each committed value as a chip.

    Every value also renders a hidden input under ``name``, so the chips post
    as a repeated form field. ``disabled`` drops both the text field and the
    per-chip remove buttons while keeping the hidden inputs.
    """

    name: str
    values: list[str] = Field(default_factory=list)
    placeholder: str = "Add…"
    remove_label: str = "Remove"
    disabled: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
