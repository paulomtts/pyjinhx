"""PJXGraph — the stage of the graph builtin: fields, DOM contract, escaping, CSS skeleton."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_badge.pjx_badge import PJXBadge
from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

NODES = '<div data-test="nodes"></div>'
EDGES = '<div data-test="edges"></div>'
CONTROLS = '<div data-test="controls"></div>'
PANEL = '<aside data-test="panel"></aside>'

CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_graph"
    / "pjx_graph.css"
)


def _html(session, **kwargs) -> str:
    base = {"id": "g", "nodes": NODES}
    base.update(kwargs)
    return render(PJXGraph(**base), session)  # type: ignore[arg-type]


def _root(parse_html, html):
    (root,) = parse_html(html)
    return root


def _test_ids(elements) -> list[str]:
    return [element.attrs.get("data-test") for element in elements]


class TestFields:
    def test_defaults(self):
        graph = PJXGraph(id="g", nodes=NODES)
        assert graph.edges == ""
        assert graph.controls == ""
        assert graph.panel == ""
        assert graph.storage_key == ""
        assert graph.scale_min == 0.2
        assert graph.scale_max == 2.0
        assert graph.aria_label == "Graph"
        assert graph.class_name == ""
        assert graph.extra_attrs == {}

    def test_nodes_is_required(self):
        with pytest.raises(ValidationError):
            PJXGraph(id="g")  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        ("scale_min", "scale_max"), [(0, 2), (-1, 2), (1, 0), (2, 1)]
    )
    def test_scale_validation_rejects(self, scale_min, scale_max):
        with pytest.raises(ValidationError):
            PJXGraph(id="g", nodes=NODES, scale_min=scale_min, scale_max=scale_max)

    @pytest.mark.parametrize(
        ("scale_min", "scale_max"), [(0.2, float("inf")), (float("inf"), float("inf"))]
    )
    def test_scale_validation_rejects_infinity(self, scale_min, scale_max):
        # str(inf) renders "inf", which the engine cannot parse as a number.
        with pytest.raises(ValidationError):
            PJXGraph(id="g", nodes=NODES, scale_min=scale_min, scale_max=scale_max)

    def test_equal_scale_bounds_are_accepted(self):
        graph = PJXGraph(id="g", nodes=NODES, scale_min=1, scale_max=1)
        assert graph.scale_min == graph.scale_max == 1.0

    def test_class_name_rejects_double_quote(self):
        with pytest.raises(ValidationError):
            PJXGraph(id="g", nodes=NODES, class_name='a"b')

    def test_extra_attrs_reject_both_quote_kinds(self):
        with pytest.raises(ValidationError):
            PJXGraph(id="g", nodes=NODES, extra_attrs={"data-x": "a\"b'c"})

    def test_extra_attrs_reject_invalid_name(self):
        with pytest.raises(ValidationError):
            PJXGraph(id="g", nodes=NODES, extra_attrs={"bad name": "x"})


class TestDomContract:
    def test_dom_contract_nesting(self, session, parse_html):
        root = _root(parse_html, _html(session, edges=EDGES))
        assert root.tag == "div"
        assert root.attrs["id"] == "g"
        assert root.classes == ["pjx-graph"]
        assert "data-pjx-graph" in root.attrs
        assert root.attrs["role"] == "group"
        assert root.attrs["aria-label"] == "Graph"

        (canvas,) = root.children
        assert canvas.tag == "div"
        assert canvas.classes == ["pjx-graph__canvas"]

        viewport = canvas.children[0]
        assert viewport.tag == "div"
        assert viewport.classes == ["pjx-graph__viewport"]

        plane, nodes, edges = viewport.children
        assert plane.tag == "svg"
        assert plane.classes == ["pjx-graph__edge-plane"]
        assert plane.attrs["aria-hidden"] == "true"
        assert nodes.attrs["data-test"] == "nodes"
        assert edges.attrs["data-test"] == "edges"

    def test_controls_inside_canvas_after_viewport(self, session, parse_html):
        root = _root(parse_html, _html(session, controls=CONTROLS))
        (canvas,) = root.children
        viewport, controls = canvas.children
        assert viewport.classes == ["pjx-graph__viewport"]
        assert controls.attrs["data-test"] == "controls"

    def test_panel_is_sibling_of_canvas(self, session, parse_html):
        root = _root(parse_html, _html(session, panel=PANEL))
        canvas, panel = root.children
        assert canvas.classes == ["pjx-graph__canvas"]
        assert panel.tag == "aside"
        assert panel.attrs["data-test"] == "panel"
        assert "panel" not in _test_ids(canvas.descendants())

    def test_single_root(self, session, parse_html):
        html = _html(session, edges=EDGES, controls=CONTROLS, panel=PANEL)
        assert len(parse_html(html)) == 1

    def test_empty_optional_slots_emit_nothing(self, session, parse_html):
        html = _html(session)
        assert html.endswith(
            '<div class="pjx-graph__canvas"><div class="pjx-graph__viewport">'
            '<svg class="pjx-graph__edge-plane" aria-hidden="true"></svg>'
            f"{NODES}</div></div></div>"
        )
        root = _root(parse_html, html)
        (canvas,) = root.children
        (viewport,) = canvas.children
        plane, nodes = viewport.children
        assert plane.tag == "svg"
        assert nodes.attrs["data-test"] == "nodes"

    def test_nodes_accepts_component(self, session, parse_html):
        layer = PJXGraphNodes(id="n", nodes_html="<b>x</b>")
        root = _root(parse_html, _html(session, nodes=layer))
        viewport = root.children[0].children[0]
        _, nodes = viewport.children
        assert nodes.attrs["id"] == "n"
        assert nodes.classes == ["pjx-graph__nodes"]
        assert [child.tag for child in nodes.children] == ["b"]

    def test_slot_strings_render_raw(self, session):
        html = _html(session, edges="<span data-pjx-graph-edge></span>")
        assert "<span data-pjx-graph-edge></span>" in html

    def test_list_slot_renders_each_component_in_order(self, session, parse_html):
        panel = [PJXBadge(id="p1", label="one"), PJXBadge(id="p2", label="two")]
        root = _root(parse_html, _html(session, panel=panel))
        canvas, first, second = root.children
        assert canvas.classes == ["pjx-graph__canvas"]
        assert [first.attrs["id"], second.attrs["id"]] == ["p1", "p2"]

    def test_id_autogenerates(self, session, parse_html):
        root = _root(parse_html, render(PJXGraph(nodes=NODES), session))
        assert re.fullmatch(r"pjx-\d+", root.attrs["id"] or "")


class TestAttributes:
    def test_storage_key_absent_when_empty(self, session):
        assert "data-pjx-graph-storage-key" not in _html(session)

    def test_storage_key_present_and_escaped(self, session, parse_html):
        html = _html(session, storage_key='k"<x>&')
        assert 'data-pjx-graph-storage-key="k&#34;&lt;x&gt;&amp;"' in html
        root = _root(parse_html, html)
        assert root.attrs["data-pjx-graph-storage-key"] == 'k"<x>&'

    def test_scale_attributes(self, session, parse_html):
        html = _html(session, scale_min=0.5, scale_max=3.0)
        assert 'data-pjx-graph-scale-min="0.5"' in html
        assert 'data-pjx-graph-scale-max="3.0"' in html

    def test_default_scale_attributes(self, session):
        html = _html(session)
        assert 'data-pjx-graph-scale-min="0.2"' in html
        assert 'data-pjx-graph-scale-max="2.0"' in html

    def test_integer_scale_bounds_render_as_floats(self, session):
        html = _html(session, scale_min=1, scale_max=3)
        assert 'data-pjx-graph-scale-min="1.0"' in html
        assert 'data-pjx-graph-scale-max="3.0"' in html

    def test_aria_label_escaped(self, session, parse_html):
        html = _html(session, aria_label='a"<b>&')
        assert 'aria-label="a&#34;&lt;b&gt;&amp;"' in html
        root = _root(parse_html, html)
        assert root.attrs["aria-label"] == 'a"<b>&'

    def test_class_name_appends(self, session, parse_html):
        root = _root(parse_html, _html(session, class_name="wide dark"))
        assert root.classes == ["pjx-graph", "wide", "dark"]

    def test_class_name_escapes_angle_and_ampersand(self, session, parse_html):
        html = _html(session, class_name="a<b&c")
        assert 'class="pjx-graph a&lt;b&amp;c"' in html
        root = _root(parse_html, html)
        assert root.attrs["class"] == "pjx-graph a<b&c"

    def test_extra_attrs_on_root(self, session, parse_html):
        html = _html(session, extra_attrs={"hx-get": "/g", "data-x": "<y>"})
        assert 'data-x="&lt;y&gt;"' in html
        root = _root(parse_html, html)
        assert root.attrs["hx-get"] == "/g"
        assert root.attrs["data-x"] == "<y>"
        assert all(
            "hx-get" not in element.attrs and "data-x" not in element.attrs
            for element in root.descendants()
        )


def _rule_block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"no rule for {selector}"
    return match.group(1)


class TestStylesheet:
    def test_css_asset_skeleton(self):
        css = CSS.read_text(encoding="utf-8")
        for token in (
            "--pjx-graph-bg",
            "--pjx-graph-border",
            "--pjx-graph-radius",
            "--pjx-graph-grid-color",
            "--pjx-graph-grid-size",
            "--pjx-graph-min-height",
        ):
            assert f"{token}:" in css
        assert "radial-gradient" in _rule_block(css, ".pjx-graph__canvas")
        assert "radial-gradient" not in _rule_block(css, ".pjx-graph__viewport")
        assert "!important" not in css
        for selector in (
            ".pjx-graph",
            ".pjx-graph__edge-plane",
            ".pjx-graph__nodes",
        ):
            _rule_block(css, selector)


def test_exported_from_the_builtins_namespace():
    from pyjinhx import builtins

    assert "PJXGraph" in builtins.__all__
    assert builtins.PJXGraph is PJXGraph
