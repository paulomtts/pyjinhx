from pydantic import Field

from pyjinhx.component import AttrValue, BaseComponent, ExtraAttrs


class PJXPasswordInput(BaseComponent):
    """A password field with a show/hide toggle button.

    The toggle flips the field between ``type="password"`` and ``type="text"``
    client-side and reports state through ``aria-pressed`` on a static label,
    following the ARIA APG toggle-button pattern.
    """

    name: str = "password"
    placeholder: str = ""
    autocomplete: str = "current-password"
    required: bool = False
    show_label: str = "Show password"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
