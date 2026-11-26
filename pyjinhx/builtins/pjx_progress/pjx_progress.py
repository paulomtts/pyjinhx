from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXProgress(BaseComponent):
    """A progress bar, or an indeterminate loading indicator when no value is given."""

    value: float | None = None
    max: float = 100
    label: str = ""
    loading_label: str = "Loading"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
