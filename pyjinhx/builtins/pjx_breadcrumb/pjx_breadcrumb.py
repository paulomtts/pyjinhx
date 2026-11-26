from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXBreadcrumb(BaseComponent):
    """A navigation trail of (label, href) crumbs where a null href marks the current page."""

    items: list[tuple[str, str | None]] = Field(default_factory=list)
    aria_label: str = "Breadcrumb"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
