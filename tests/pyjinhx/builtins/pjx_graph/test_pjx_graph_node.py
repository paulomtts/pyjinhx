"""PJXGraphNode — one node card of the graph builtin: fields, DOM contract, escaping, CSS."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode

REQUIRED = {"node_id": "a", "x": 10, "y": 20.5, "title": "Start"}


def _node(**kwargs) -> PJXGraphNode:
    base = {"id": "n", **REQUIRED}
    base.update(kwargs)
    return PJXGraphNode(**base)  # type: ignore[arg-type]


class TestFields:
    def test_defaults(self):
        node = _node()
        assert node.node_type == ""
        assert node.eyebrow == ""
        assert node.summary is None
        assert node.color == ""
        assert node.icon == ""
        assert node.in_port is False
        assert node.out_ports == ()
        assert node.class_name == ""
        assert node.extra_attrs == {}

    @pytest.mark.parametrize("missing", sorted(REQUIRED))
    def test_requires_node_id_position_and_title(self, missing):
        kwargs = {name: value for name, value in REQUIRED.items() if name != missing}
        with pytest.raises(ValidationError):
            PJXGraphNode(id="n", **kwargs)  # type: ignore[arg-type]

    @pytest.mark.parametrize("node_id", ["", 'a"b'])
    def test_node_id_rejects_empty_and_double_quote(self, node_id):
        with pytest.raises(ValidationError):
            _node(node_id=node_id)

    @pytest.mark.parametrize("position", [{"x": float("inf")}, {"y": float("nan")}])
    def test_position_rejects_non_finite(self, position):
        with pytest.raises(ValidationError):
            _node(**position)

    def test_int_position_coerces_to_float(self):
        node = _node(x=120)
        assert node.x == 120.0
        assert isinstance(node.x, float)

    def test_node_type_rejects_double_quote(self):
        with pytest.raises(ValidationError):
            _node(node_type='a"b')

    @pytest.mark.parametrize("color", ['red"', "red;position:fixed"])
    def test_color_rejects_double_quote_and_semicolon(self, color):
        with pytest.raises(ValidationError):
            _node(color=color)

    @pytest.mark.parametrize(
        "color", ["var(--brand)", "rgb(1 2 3 / 50%)", "hsl(200, 50%, 40%)", "#f00"]
    )
    def test_color_accepts_css_expressions(self, color):
        assert _node(color=color).color == color

    @pytest.mark.parametrize("out_ports", [("",), ('a"b',), ("ok", "ok")])
    def test_out_ports_reject_empty_quote_and_duplicate_keys(self, out_ports):
        with pytest.raises(ValidationError):
            _node(out_ports=out_ports)

    def test_out_ports_accept_a_list(self):
        assert _node(out_ports=["yes", "no"]).out_ports == ("yes", "no")

    def test_class_name_rejects_double_quote(self):
        with pytest.raises(ValidationError):
            _node(class_name='a"b')

    def test_extra_attrs_reject_both_quote_kinds_and_invalid_name(self):
        with pytest.raises(ValidationError):
            _node(extra_attrs={"data-x": "a\"b'c"})
        with pytest.raises(ValidationError):
            _node(extra_attrs={"bad name": "x"})
