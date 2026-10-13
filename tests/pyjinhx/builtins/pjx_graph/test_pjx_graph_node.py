"""PJXGraphNode — one node card of the graph builtin: fields, DOM contract, escaping, CSS."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_badge.pjx_badge import PJXBadge
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

REQUIRED = {"node_id": "a", "x": 10, "y": 20.5, "title": "Start"}

CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_graph_node"
    / "pjx_graph_node.css"
)


def _node(**kwargs) -> PJXGraphNode:
    base = {"id": "n", **REQUIRED}
    base.update(kwargs)
    return PJXGraphNode(**base)  # type: ignore[arg-type]


def _html(session, **kwargs) -> str:
    return render(_node(**kwargs), session)


def _root(parse_html, html):
    (root,) = parse_html(html)
    return root


def _ports(root, direction: str):
    return [
        element
        for element in root.descendants()
        if element.attrs.get("data-pjx-graph-port") == direction
    ]


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


class TestMarkup:
    def test_root_contract(self, session, parse_html):
        html = _html(session)
        assert html == (
            '<div id="n" class="pjx-graph__node" data-node-id="a" data-node-type=""'
            ' data-x="10.0" data-y="20.5"'
            ' style="--pjx-graph-node-x:10.0px;--pjx-graph-node-y:20.5px;">'
            '<div class="pjx-graph__node-body">'
            '<span class="pjx-graph__node-title">Start</span>'
            "</div></div>"
        )
        root = _root(parse_html, html)
        assert root.tag == "div"
        assert root.classes == ["pjx-graph__node"]
        assert root.attrs["data-node-id"] == "a"
        assert root.attrs["data-node-type"] == ""
        assert root.attrs["data-x"] == "10.0"
        assert root.attrs["data-y"] == "20.5"
        assert "--pjx-graph-node-color" not in root.attrs["style"]
        (body,) = root.children
        assert body.classes == ["pjx-graph__node-body"]
        (title,) = body.children
        assert title.tag == "span"
        assert title.classes == ["pjx-graph__node-title"]

    @pytest.mark.parametrize("color", ["#f00", "var(--brand)", "rgb(1 2 3 / 50%)"])
    def test_color_sets_custom_property(self, session, parse_html, color):
        root = _root(parse_html, _html(session, color=color))
        assert root.attrs["style"] == (
            "--pjx-graph-node-x:10.0px;--pjx-graph-node-y:20.5px;"
            f"--pjx-graph-node-color:{color};"
        )

    @pytest.mark.parametrize("value", [-35.25, 0.1 + 0.2, 1e-07, 1e21])
    def test_coordinates_round_trip(self, session, parse_html, value):
        root = _root(parse_html, _html(session, x=value, y=value))
        for axis in ("x", "y"):
            rendered = root.attrs[f"data-{axis}"]
            assert float(rendered) == value
            assert f"--pjx-graph-node-{axis}:{rendered}px;" in root.attrs["style"]

    def test_text_props_are_escaped(self, session, parse_html):
        html = _html(session, title="<b>&", eyebrow="<b>&", summary="<b>&")
        assert '<span class="pjx-graph__node-title">&lt;b&gt;&amp;</span>' in html
        assert '<span class="pjx-graph__node-eyebrow">&lt;b&gt;&amp;</span>' in html
        assert '<p class="pjx-graph__node-summary">&lt;b&gt;&amp;</p>' in html
        root = _root(parse_html, html)
        assert all(element.tag != "b" for element in root.descendants())

    def test_attribute_props_are_escaped(self, session, parse_html):
        html = _html(
            session,
            node_id="a<b&c",
            node_type="t<&",
            color="c<&",
            out_ports=("p<&",),
            class_name="k<&",
            extra_attrs={"data-k": "<y>&"},
        )
        assert 'data-node-id="a&lt;b&amp;c"' in html
        assert 'data-node-type="t&lt;&amp;"' in html
        assert "--pjx-graph-node-color:c&lt;&amp;;" in html
        assert 'data-port="p&lt;&amp;"' in html
        assert 'class="pjx-graph__node k&lt;&amp;"' in html
        assert 'data-k="&lt;y&gt;&amp;"' in html
        root = _root(parse_html, html)
        assert root.attrs["data-node-id"] == "a<b&c"
        assert root.attrs["data-node-type"] == "t<&"
        assert root.attrs["style"].endswith("--pjx-graph-node-color:c<&;")
        assert [port.attrs["data-port"] for port in _ports(root, "out")] == ["p<&"]
        assert root.classes == ["pjx-graph__node", "k<&"]
        assert root.attrs["data-k"] == "<y>&"

    def test_single_quote_and_unicode_survive(self, session, parse_html):
        html = _html(session, title="Café's ✓", out_ports=("it's", "größer"))
        assert "Café&#39;s ✓" in html
        root = _root(parse_html, html)
        assert [port.attrs["data-port"] for port in _ports(root, "out")] == [
            "it's",
            "größer",
        ]

    def test_summary_none_omits_element_and_empty_renders_it(self, session, parse_html):
        assert "pjx-graph__node-summary" not in _html(session)
        root = _root(parse_html, _html(session, summary=""))
        (body,) = root.children
        summary = body.children[-1]
        assert summary.tag == "p"
        assert summary.classes == ["pjx-graph__node-summary"]
        assert '<p class="pjx-graph__node-summary"></p>' in _html(session, summary="")

    def test_eyebrow_and_icon_omitted_when_empty_and_rendered_when_set(
        self, session, parse_html
    ):
        html = _html(session)
        assert "pjx-graph__node-eyebrow" not in html
        assert "pjx-graph__node-icon" not in html

        html = _html(session, icon="<svg data-i></svg>", eyebrow="Agent")
        assert '<span class="pjx-graph__node-icon"><svg data-i></svg></span>' in html
        root = _root(parse_html, html)
        icon, body = root.children
        assert icon.classes == ["pjx-graph__node-icon"]
        assert [child.tag for child in icon.children] == ["svg"]
        assert [child.classes for child in body.children] == [
            ["pjx-graph__node-eyebrow"],
            ["pjx-graph__node-title"],
        ]
        assert '<span class="pjx-graph__node-eyebrow">Agent</span>' in html

    def test_icon_accepts_a_component(self, session, parse_html):
        html = _html(session, icon=PJXBadge(id="b", label="B"))
        root = _root(parse_html, html)
        icon = root.children[0]
        assert icon.classes == ["pjx-graph__node-icon"]
        (badge,) = icon.children
        assert badge.attrs["id"] == "b"
        assert "&lt;" not in html

    def test_in_port_markup(self, session, parse_html):
        root = _root(parse_html, _html(session, in_port=True))
        (port,) = _ports(root, "in")
        assert root.children[0] is port
        assert port.tag == "span"
        assert port.classes == ["pjx-graph__port", "pjx-graph__port--in"]
        assert "data-port" not in port.attrs

    def test_out_ports_markup_in_order(self, session, parse_html):
        root = _root(parse_html, _html(session, out_ports=("yes", "no")))
        container = root.children[-1]
        assert container.tag == "div"
        assert container.classes == ["pjx-graph__node-ports"]
        assert container.children == _ports(root, "out")
        assert [port.attrs["data-port"] for port in container.children] == ["yes", "no"]
        for port in container.children:
            assert port.tag == "span"
            assert port.classes == ["pjx-graph__port", "pjx-graph__port--out"]

    def test_no_ports_by_default(self, session, parse_html):
        html = _html(session)
        assert "data-pjx-graph-port" not in html
        assert "pjx-graph__node-ports" not in html

    def test_class_name_appends(self, session, parse_html):
        root = _root(parse_html, _html(session, class_name="extra more"))
        assert root.classes == ["pjx-graph__node", "extra", "more"]

    def test_extra_attrs_on_root(self, session, parse_html):
        root = _root(
            parse_html, _html(session, extra_attrs={"hx-get": "/n", "data-k": "it's"})
        )
        assert root.attrs["hx-get"] == "/n"
        assert root.attrs["data-k"] == "it's"

    def test_renders_inside_node_layer(self, session, parse_html):
        a = render(_node(id="na", node_id="a"), session)
        b = render(_node(id="nb", node_id="b"), session)
        layer = PJXGraphNodes(id="layer", nodes_html=PJXGraphNodes.join([a, b]))
        root = _root(parse_html, render(layer, session))
        assert [child.attrs["data-node-id"] for child in root.children] == ["a", "b"]


def _rule_block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"no rule for {selector}"
    return match.group(1)


class TestStylesheet:
    def test_css_asset_skeleton(self):
        css = CSS.read_text(encoding="utf-8")
        tokens = _rule_block(css, ":where(:root)")
        for token in (
            "--pjx-graph-node-bg: var(--surface);",
            "--pjx-graph-node-border: var(--border);",
            "--pjx-graph-node-radius: var(--radius-md);",
            "--pjx-graph-node-width:",
            "--pjx-graph-node-muted: var(--text-muted);",
            "--pjx-graph-port-size:",
            "--pjx-graph-port-bg: var(--surface);",
        ):
            assert token in tokens
        node = _rule_block(css, ".pjx-graph__node")
        assert "position: absolute" in node
        assert "var(--pjx-graph-node-x" in node
        assert "var(--pjx-graph-node-y" in node
        assert "var(--pjx-graph-node-color, var(--pjx-graph-node-border))" in node
        for selector in (
            ".pjx-graph__node-icon",
            ".pjx-graph__node-body",
            ".pjx-graph__node-eyebrow",
            ".pjx-graph__node-title",
            ".pjx-graph__node-summary",
            ".pjx-graph__node-ports",
            ".pjx-graph__port",
            ".pjx-graph__port--in",
            ".pjx-graph__port--out",
        ):
            _rule_block(css, selector)
        assert "!important" not in css
        assert "pjx-icon" not in css
        assert "--muted-foreground" not in css

    def test_rendering_registers_stylesheet(self, session):
        from pyjinhx.session import accumulate_assets

        assert PJXGraphNode.__pjx_descriptor__.css_paths == (CSS,)
        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert CSS in session.css_assets


def test_exported_from_the_builtins_namespace():
    from pyjinhx import builtins

    assert "PJXGraphNode" in builtins.__all__
    assert builtins.PJXGraphNode is PJXGraphNode
