from pydantic import Field, field_validator

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXGraphNode(BaseComponent):
    """One node card of a :class:`PJXGraph`, absolutely positioned at ``(x, y)``.

    The root's ``data-node-id``, ``data-x``/``data-y`` and port handles are the
    DOM the graph engine reads. ``summary=None`` omits the summary line, while
    ``""`` renders it empty. ``icon`` is raw HTML; every other text is escaped.
    """

    node_id: AttrValue = Field(min_length=1)
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    node_type: AttrValue = ""
    title: str
    eyebrow: str = ""
    summary: str | None = None
    color: AttrValue = ""
    icon: Slot = ""
    in_port: bool = False
    out_ports: tuple[AttrValue, ...] = ()
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str) -> str:
        """Reject a colour that could end its declaration in the root's style attribute."""
        if ";" in value:
            raise ValueError("color must not contain ';'")
        return value

    @field_validator("out_ports")
    @classmethod
    def _check_out_ports(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject empty or repeated out-port keys."""
        if "" in value:
            raise ValueError("out_ports keys must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("out_ports keys must be unique")
        return value
