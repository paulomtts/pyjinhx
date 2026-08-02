from pydantic import Field

from pyjinhx2.component import AttrValue, BaseComponent, ExtraAttrs


class PJXRegionLoader(BaseComponent):
    """An overlay spinner that covers its nearest positioned ancestor.

    The parent must be non-statically positioned for the overlay to cover it.
    Visibility is driven from the client by ``pjx.loader.region``.
    """

    aria_label: str = "Loading"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
