from pydantic import Field, field_validator

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, validate_attr_value

_EDGE_KEYS = frozenset({"id", "from", "to", "port", "state", "label"})


class PJXGraphEdges(BaseComponent):
    """The edge layer of a :class:`PJXGraph`: one hidden ``span`` per edge.

    Each edge is a dict with ``id``, ``from`` and ``to`` (required) and
    optional ``port``, ``state`` and ``label``. The graph engine reads the
    spans' ``data-*`` attributes and draws the edges; nothing here is visible.
    Apps subclass it to make the layer reactive.
    """

    edges: list[dict[str, str]] = Field(default_factory=list)
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @field_validator("edges")
    @classmethod
    def _check_edges(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        """Reject unknown keys, missing endpoints, quoted identifiers and repeated ids."""
        seen: set[str] = set()
        for edge in value:
            unknown = sorted(edge.keys() - _EDGE_KEYS)
            if unknown:
                raise ValueError(f"unknown edge keys: {', '.join(unknown)}")
            for key in ("id", "from", "to"):
                if not edge.get(key):
                    raise ValueError(f"edge {key!r} is required and must not be empty")
            for key in ("id", "from", "to", "port", "state"):
                validate_attr_value(edge.get(key, ""))
            if edge["id"] in seen:
                raise ValueError(f"duplicate edge id {edge['id']!r}")
            seen.add(edge["id"])
        return value
