from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXGraphControls(BaseComponent):
    """Zoom in, zoom out and fit buttons that float over a :class:`PJXGraph` canvas.

    Pass it as the graph's ``controls`` slot. The buttons carry
    ``data-pjx-graph-zoom="in"``, ``data-pjx-graph-zoom="out"`` and
    ``data-pjx-graph-fit``, which the graph engine acts on; they work only
    inside a mounted ``PJXGraph``. Each label is escaped text and is also its
    button's ``aria-label``.
    """

    zoom_in_label: str = "Zoom in"
    zoom_out_label: str = "Zoom out"
    fit_label: str = "Fit"
    aria_label: str = "Graph controls"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
