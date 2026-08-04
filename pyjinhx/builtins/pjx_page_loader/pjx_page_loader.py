from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXPageLoader(BaseComponent):
    """A full-viewport overlay spinner driven by htmx navigation traffic.

    Ships active when ``active_on_load`` so a cold page load is covered until
    ``DOMContentLoaded``; afterwards visibility is ref-counted from the client
    by ``pjx.loader.page``.
    """

    nav_targets: str = "app-content"
    active_on_load: bool = True
    loading_label: str = "Loading"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
