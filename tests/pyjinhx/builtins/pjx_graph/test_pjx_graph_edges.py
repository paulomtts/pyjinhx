"""PJXGraphEdges — the edge layer of the graph builtin: fields, DOM contract, escaping."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_edges import PJXGraphEdges
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

EDGE = {"id": "e1", "from": "a", "to": "b"}


def _edges(*edges: dict, **kwargs) -> PJXGraphEdges:
    return PJXGraphEdges(id="e", edges=list(edges), **kwargs)  # type: ignore[arg-type]


DATA_ATTRS = (
    "data-edge-id",
    "data-from",
    "data-to",
    "data-port",
    "data-state",
    "data-label",
)


def _html(session, *edges: dict, **kwargs) -> str:
    return render(_edges(*edges, **kwargs), session)


def _root(parse_html, html):
    (root,) = parse_html(html)
    return root


def _data(span) -> dict:
    return {name: span.attrs[name] for name in DATA_ATTRS}


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


class TestMarkup:
    def test_empty_layer_renders_hidden_container(self, session, parse_html):
        html = _html(session)
        assert html == '<div id="e" class="pjx-graph__edges" hidden></div>'
        root = _root(parse_html, html)
        assert root.children == []

    def test_root_contract(self, session, parse_html):
        html = _html(session, EDGE)
        assert html == (
            '<div id="e" class="pjx-graph__edges" hidden>'
            '<span hidden data-pjx-graph-edge data-edge-id="e1" data-from="a"'
            ' data-to="b" data-port="" data-state="" data-label=""></span>'
            "</div>"
        )
        root = _root(parse_html, html)
        assert root.tag == "div"
        assert root.attrs["id"] == "e"
        assert "hidden" in root.attrs
        assert root.classes == ["pjx-graph__edges"]

    def test_one_span_per_edge_in_order(self, session, parse_html):
        edges = [{**EDGE, "id": edge_id} for edge_id in ("e3", "e1", "e2")]
        root = _root(parse_html, _html(session, *edges))
        assert [span.attrs["data-edge-id"] for span in root.children] == [
            "e3",
            "e1",
            "e2",
        ]
        for span in root.children:
            assert span.tag == "span"
            assert "hidden" in span.attrs
            assert "data-pjx-graph-edge" in span.attrs
            assert span.children == []

    def test_all_edge_attributes_rendered(self, session, parse_html):
        edge = {
            "id": "e1",
            "from": "a",
            "to": "b",
            "port": "yes",
            "state": "active",
            "label": "Approved",
        }
        root = _root(parse_html, _html(session, edge))
        (span,) = root.children
        assert _data(span) == {
            "data-edge-id": "e1",
            "data-from": "a",
            "data-to": "b",
            "data-port": "yes",
            "data-state": "active",
            "data-label": "Approved",
        }

    def test_missing_optional_keys_render_empty(self, session, parse_html):
        root = _root(parse_html, _html(session, EDGE))
        (span,) = root.children
        assert span.attrs["data-port"] == ""
        assert span.attrs["data-state"] == ""
        assert span.attrs["data-label"] == ""

    def test_explicit_empty_optional_values_render_like_missing(self, session):
        explicit = {**EDGE, "port": "", "state": "", "label": ""}
        assert _html(session, explicit) == _html(session, EDGE)

    def test_attribute_order_ignores_input_key_order(self, session):
        shuffled = {
            "label": "L",
            "to": "b",
            "state": "s",
            "id": "e1",
            "port": "p",
            "from": "a",
        }
        html = _html(session, shuffled)
        assert (
            '<span hidden data-pjx-graph-edge data-edge-id="e1" data-from="a"'
            ' data-to="b" data-port="p" data-state="s" data-label="L"></span>'
        ) in html

    def test_values_are_escaped(self, session, parse_html):
        edge = {
            "id": "i<&",
            "from": "f<&",
            "to": "t<&",
            "port": "p<&",
            "state": "s<&",
            "label": '<b> & "q"',
        }
        html = _html(session, edge)
        assert 'data-edge-id="i&lt;&amp;"' in html
        assert 'data-from="f&lt;&amp;"' in html
        assert 'data-to="t&lt;&amp;"' in html
        assert 'data-port="p&lt;&amp;"' in html
        assert 'data-state="s&lt;&amp;"' in html
        assert 'data-label="&lt;b&gt; &amp; &#34;q&#34;"' in html
        root = _root(parse_html, html)
        (span,) = root.children
        assert span.children == []
        assert _data(span) == {
            "data-edge-id": "i<&",
            "data-from": "f<&",
            "data-to": "t<&",
            "data-port": "p<&",
            "data-state": "s<&",
            "data-label": '<b> & "q"',
        }

    def test_label_cannot_close_the_span_or_container(self, session, parse_html):
        label = "</span></div><script>x</script>"
        html = _html(session, {**EDGE, "label": label})
        assert "<script>" not in html
        root = _root(parse_html, html)
        (span,) = root.children
        assert span.children == []
        assert span.attrs["data-label"] == label

    def test_single_quote_and_unicode_survive(self, session, parse_html):
        edge = {**EDGE, "port": "it's", "state": "größer", "label": "it's ✓"}
        html = _html(session, edge)
        assert 'data-port="it&#39;s"' in html
        root = _root(parse_html, html)
        (span,) = root.children
        assert span.attrs["data-port"] == "it's"
        assert span.attrs["data-state"] == "größer"
        assert span.attrs["data-label"] == "it's ✓"

    def test_class_name_appends(self, session, parse_html):
        root = _root(parse_html, _html(session, class_name="extra more"))
        assert root.classes == ["pjx-graph__edges", "extra", "more"]
        html = _html(session, class_name="k<&")
        assert 'class="pjx-graph__edges k&lt;&amp;"' in html

    def test_extra_attrs_on_root_escaped(self, session, parse_html):
        html = _html(session, extra_attrs={"hx-swap-oob": "true", "data-k": "<y>&"})
        assert html == (
            '<div id="e" class="pjx-graph__edges" hidden hx-swap-oob="true"'
            ' data-k="&lt;y&gt;&amp;"></div>'
        )
        root = _root(parse_html, html)
        assert root.attrs["hx-swap-oob"] == "true"
        assert root.attrs["data-k"] == "<y>&"

    def test_renders_inside_graph_viewport(self, session, parse_html):
        graph = PJXGraph(
            id="g",
            nodes=PJXGraphNodes(id="layer"),
            edges=_edges(EDGE),
        )
        root = _root(parse_html, render(graph, session))
        (canvas,) = root.children
        viewport = canvas.children[0]
        assert viewport.classes == ["pjx-graph__viewport"]
        plane, nodes, edges = viewport.children
        assert plane.tag == "svg"
        assert nodes.classes == ["pjx-graph__nodes"]
        assert edges.classes == ["pjx-graph__edges"]
        assert [span.attrs["data-edge-id"] for span in edges.children] == ["e1"]
