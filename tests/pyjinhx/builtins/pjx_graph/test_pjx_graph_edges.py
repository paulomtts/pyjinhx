"""PJXGraphEdges — the edge layer of the graph builtin: fields, DOM contract, escaping."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_graph_edges import PJXGraphEdges

EDGE = {"id": "e1", "from": "a", "to": "b"}


def _edges(*edges: dict, **kwargs) -> PJXGraphEdges:
    return PJXGraphEdges(id="e", edges=list(edges), **kwargs)  # type: ignore[arg-type]


class TestFields:
    def test_defaults(self):
        layer = PJXGraphEdges()
        assert layer.edges == []
        assert layer.class_name == ""
        assert layer.extra_attrs == {}

    def test_edges_keep_input_order_and_keys(self):
        full = {
            "id": "e2",
            "from": "b",
            "to": "c",
            "port": "yes",
            "state": "active",
            "label": "Go",
        }
        edges = [full, dict(EDGE)]
        layer = _edges(*edges)
        assert layer.edges == edges
        assert list(layer.edges[0]) == ["id", "from", "to", "port", "state", "label"]
        assert list(layer.edges[1]) == ["id", "from", "to"]

    @pytest.mark.parametrize("missing", ["id", "from", "to"])
    def test_requires_id_from_and_to(self, missing):
        edge = {key: value for key, value in EDGE.items() if key != missing}
        with pytest.raises(ValidationError, match=f"edge '{missing}' is required"):
            _edges(edge)

    @pytest.mark.parametrize("key", ["id", "from", "to"])
    def test_rejects_empty_required_values(self, key):
        with pytest.raises(ValidationError, match=f"edge '{key}' is required"):
            _edges({**EDGE, key: ""})

    def test_rejects_unknown_key(self):
        with pytest.raises(ValidationError, match="unknown edge keys: source"):
            _edges({**EDGE, "source": "a"})

    @pytest.mark.parametrize("override", [{"id": 1}, {"port": None}])
    def test_rejects_non_string_values(self, override):
        with pytest.raises(ValidationError):
            _edges({**EDGE, **override})

    @pytest.mark.parametrize("key", ["id", "from", "to", "port", "state"])
    def test_identifier_values_reject_double_quote(self, key):
        with pytest.raises(ValidationError, match="must not contain"):
            _edges({**EDGE, key: 'x"y'})

    def test_label_accepts_double_quote(self):
        layer = _edges({**EDGE, "label": 'say "hi"'})
        assert layer.edges[0]["label"] == 'say "hi"'

    def test_rejects_duplicate_edge_ids(self):
        with pytest.raises(ValidationError, match="duplicate edge id 'e1'"):
            _edges(EDGE, {**EDGE, "from": "c"})

    def test_accepts_self_loop_and_unknown_state(self):
        layer = _edges({"id": "loop", "from": "a", "to": "a", "state": "whatever"})
        assert layer.edges[0]["to"] == "a"
        assert layer.edges[0]["state"] == "whatever"

    def test_ids_are_not_normalised(self):
        ids = ["e1", "E1", " e1"]
        layer = _edges(*({**EDGE, "id": edge_id} for edge_id in ids))
        assert [edge["id"] for edge in layer.edges] == ids

    @pytest.mark.parametrize("edges", [None, ["e1"], [("id", "e1")]])
    def test_rejects_non_dict_edges(self, edges):
        with pytest.raises(ValidationError):
            PJXGraphEdges(edges=edges)  # type: ignore[arg-type]

    def test_class_name_rejects_double_quote(self):
        with pytest.raises(ValidationError):
            _edges(class_name='a"b')

    def test_extra_attrs_reject_both_quote_kinds_and_invalid_name(self):
        with pytest.raises(ValidationError):
            _edges(extra_attrs={"data-x": "a\"b'c"})
        with pytest.raises(ValidationError):
            _edges(extra_attrs={"bad name": "x"})
