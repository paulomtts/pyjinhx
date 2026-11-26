from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXSegmentedControl(BaseComponent):
    """A radiogroup rendered as a row of mutually exclusive segments.

    Each ``options`` entry is a ``(value, label)`` pair; ``selected`` names the
    value whose radio carries ``checked``. A JSON-string ``options`` (the
    inline-attr path) is decoded by the core's generic
    ``BaseComponent._coerce_json_string_attrs`` — no component-local coercion
    needed here.
    """

    name: str
    options: list[tuple[str, str]] = Field(default_factory=list)
    selected: str = ""
    disabled: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
