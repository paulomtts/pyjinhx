"""PJXGraphControls — the graph's zoom and fit buttons: fields, DOM contract, escaping, CSS."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_controls import PJXGraphControls
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_graph_controls"
    / "pjx_graph_controls.css"
)


def _html(session, **kwargs) -> str:
    return render(PJXGraphControls(id="c", **kwargs), session)


def _root(parse_html, html):
    (root,) = parse_html(html)
    return root


class TestFields:
    def test_defaults(self):
        controls = PJXGraphControls()
        assert controls.zoom_in_label == "Zoom in"
        assert controls.zoom_out_label == "Zoom out"
        assert controls.fit_label == "Fit"
        assert controls.aria_label == "Graph controls"
        assert controls.class_name == ""
        assert controls.extra_attrs == {}

    def test_class_name_rejects_double_quote(self):
        with pytest.raises(ValidationError):
            PJXGraphControls(class_name='a"b')

    def test_extra_attrs_reject_both_quote_kinds_and_invalid_name(self):
        with pytest.raises(ValidationError):
            PJXGraphControls(extra_attrs={"data-x": "a\"b'c"})
        with pytest.raises(ValidationError):
            PJXGraphControls(extra_attrs={"bad name": "x"})


class TestMarkup:
    def test_dom_contract(self, session):
        assert _html(session) == (
            '<div id="c" role="group" aria-label="Graph controls"'
            ' class="pjx-graph__controls" data-pjx-graph-controls>'
            '<button type="button" class="pjx-graph__control"'
            ' data-pjx-graph-zoom="in" aria-label="Zoom in">Zoom in</button>'
            '<button type="button" class="pjx-graph__control"'
            ' data-pjx-graph-zoom="out" aria-label="Zoom out">Zoom out</button>'
            '<button type="button" class="pjx-graph__control"'
            ' data-pjx-graph-fit aria-label="Fit">Fit</button>'
            "</div>"
        )

    def test_single_root(self, session, parse_html):
        root = _root(parse_html, _html(session))
        assert root.tag == "div"
        assert root.attrs["id"] == "c"
        assert root.attrs["role"] == "group"
        assert root.attrs["aria-label"] == "Graph controls"
        assert "data-pjx-graph-controls" in root.attrs
        assert root.classes == ["pjx-graph__controls"]

    def test_three_buttons_in_order(self, session, parse_html):
        root = _root(parse_html, _html(session))
        zoom_in, zoom_out, fit = root.children
        for button in (zoom_in, zoom_out, fit):
            assert button.tag == "button"
            assert button.attrs["type"] == "button"
            assert button.classes == ["pjx-graph__control"]
            assert button.children == []
        assert zoom_in.attrs["data-pjx-graph-zoom"] == "in"
        assert zoom_out.attrs["data-pjx-graph-zoom"] == "out"
        assert "data-pjx-graph-fit" in fit.attrs
        assert "data-pjx-graph-zoom" not in fit.attrs
        assert [b.attrs["aria-label"] for b in root.children] == [
            "Zoom in",
            "Zoom out",
            "Fit",
        ]

    def test_label_props_replace_text_and_aria_label(self, session, parse_html):
        html = _html(
            session,
            zoom_in_label="Plus",
            zoom_out_label="Minus",
            fit_label="Frame",
            aria_label="Zoom",
        )
        assert ">Plus</button>" in html
        assert ">Minus</button>" in html
        assert ">Frame</button>" in html
        root = _root(parse_html, html)
        assert root.attrs["aria-label"] == "Zoom"
        assert [b.attrs["aria-label"] for b in root.children] == [
            "Plus",
            "Minus",
            "Frame",
        ]

    def test_labels_are_escaped(self, session, parse_html):
        label = '<b>&"x'
        escaped = "&lt;b&gt;&amp;&#34;x"
        html = _html(
            session,
            zoom_in_label=label,
            zoom_out_label=label,
            fit_label=label,
            aria_label=label,
        )
        assert "<b>" not in html
        assert html.count(f'aria-label="{escaped}"') == 4
        assert html.count(f">{escaped}</button>") == 3
        root = _root(parse_html, html)
        assert all(el.tag != "b" for el in root.descendants())
        assert root.attrs["aria-label"] == label
        assert [b.attrs["aria-label"] for b in root.children] == [label] * 3

    def test_class_name_appends(self, session, parse_html):
        root = _root(parse_html, _html(session, class_name="extra more"))
        assert root.classes == ["pjx-graph__controls", "extra", "more"]
        assert 'class="pjx-graph__controls k&lt;&amp;"' in _html(
            session, class_name="k<&"
        )

    def test_extra_attrs_on_root_escaped(self, session, parse_html):
        html = _html(session, extra_attrs={"hx-swap-oob": "true", "data-k": "<y>&"})
        assert (
            ' data-pjx-graph-controls hx-swap-oob="true" data-k="&lt;y&gt;&amp;">'
            in html
        )
        root = _root(parse_html, html)
        assert root.attrs["hx-swap-oob"] == "true"
        assert root.attrs["data-k"] == "<y>&"
        assert all("hx-swap-oob" not in b.attrs for b in root.children)

    def test_id_autogenerates(self, session, parse_html):
        root = _root(parse_html, render(PJXGraphControls(), session))
        assert root.attrs["id"]

    def test_renders_as_the_canvas_last_child(self, session, parse_html):
        graph = PJXGraph(
            id="g",
            nodes=PJXGraphNodes(id="layer"),
            controls=PJXGraphControls(id="c"),
        )
        root = _root(parse_html, render(graph, session))
        (canvas,) = root.children
        viewport, controls = canvas.children
        assert viewport.classes == ["pjx-graph__viewport"]
        assert controls.attrs["id"] == "c"
        assert controls.classes == ["pjx-graph__controls"]


def _rule_block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"no rule for {selector}"
    return match.group(1)


class TestStylesheet:
    def test_css_asset_skeleton(self):
        css = CSS.read_text(encoding="utf-8")
        tokens = _rule_block(css, ":where(:root)")
        for token in (
            "--pjx-graph-controls-bg: var(--surface);",
            "--pjx-graph-controls-border: var(--border);",
            "--pjx-graph-controls-radius: var(--radius-md);",
            "--pjx-graph-controls-color: var(--text-muted);",
            "--pjx-graph-controls-inset:",
            "--pjx-graph-controls-gap:",
        ):
            assert token in tokens
        group = _rule_block(css, ".pjx-graph__controls")
        assert "position: absolute" in group
        assert "right: var(--pjx-graph-controls-inset)" in group
        assert "bottom: var(--pjx-graph-controls-inset)" in group
        assert "z-index:" in group
        assert "flex-direction: column" in group
        _rule_block(css, ".pjx-graph__control")
        assert "!important" not in css
        assert "pjx-icon" not in css

    def test_rendering_registers_stylesheet(self, session):
        from pyjinhx.session import accumulate_assets

        assert PJXGraphControls.__pjx_descriptor__.css_paths == (CSS,)
        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert CSS in session.css_assets


def test_exported_from_the_builtins_namespace():
    from pyjinhx import builtins

    names = builtins.__all__
    assert names.index("PJXGraphControls") == names.index("PJXGraph") + 1
    assert names.index("PJXGraphEdges") == names.index("PJXGraphControls") + 1
    assert builtins.PJXGraphControls is PJXGraphControls
