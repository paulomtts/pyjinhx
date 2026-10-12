from pydantic import Field, model_validator

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXGraph(BaseComponent):
    """The stage of a pan/zoom node graph: canvas, viewport, node and edge layers.

    The server emits static markup only; the graph engine finds the stage by
    its ``data-pjx-graph*`` markers. ``panel`` renders beside the canvas rather
    than inside it, so clicks in the panel never reach the engine's listeners.
    An empty ``storage_key`` disables persistence.
    """

    nodes: Slot
    edges: Slot = ""
    controls: Slot = ""
    panel: Slot = ""
    storage_key: str = ""
    scale_min: float = Field(default=0.2, gt=0, allow_inf_nan=False)
    scale_max: float = Field(default=2.0, gt=0, allow_inf_nan=False)
    aria_label: str = "Graph"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_scale_range(self) -> "PJXGraph":
        """Reject a zoom range whose minimum exceeds its maximum."""
        if self.scale_min > self.scale_max:
            raise ValueError("scale_min must not exceed scale_max")
        return self
