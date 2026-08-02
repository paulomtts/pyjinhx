from pyjinhx2.component import AttrValue, BaseComponent


class PJXProgress(BaseComponent):
    """A progress bar, or an indeterminate loading indicator when no value is given."""

    value: float | None = None
    max: float = 100
    label: str = ""
    loading_label: str = "Loading"
    class_name: AttrValue = ""
