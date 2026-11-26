from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXFormField(BaseComponent):
    """A label + control + help/error wrapper around one form input.

    ``content`` is an opaque slot: the control itself (raw markup or a nested
    component) is composed by the caller. ``error`` and ``help`` are mutually
    exclusive — an error replaces the help text rather than stacking with it.
    """

    label: str = ""
    for_id: str = ""
    content: Slot = ""
    help: str = ""
    error: str = ""
    required: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
