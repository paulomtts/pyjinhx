from collections.abc import Iterable

from markupsafe import Markup
from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXGraphNodes(BaseComponent):
    """The node layer of a :class:`PJXGraph`: a stable container of node markup.

    It renders even when empty, so the graph engine and out-of-band swaps
    always have a target. Apps subclass it to make the layer reactive.
    """

    nodes_html: Slot = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @staticmethod
    def join(parts: Iterable[str]) -> Markup:
        """Concatenate already-rendered node markup, in order, without escaping it."""
        # render() returns plain str, which Markup("").join would escape.
        return Markup("").join(Markup(part) for part in parts)
