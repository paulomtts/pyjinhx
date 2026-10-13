"""PJXGraphSidePanel — the graph's floating side panel: fields, DOM contract, escaping, CSS."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx._component import _resolve_children_field
from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_controls import PJXGraphControls
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.builtins.ui.pjx_graph_side_panel import PJXGraphSidePanel
from pyjinhx.rendering import render

CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_graph_side_panel"
    / "pjx_graph_side_panel.css"
)

CLOSED = (
    '<aside id="p" aria-label="Graph panel" class="pjx-graph__panel"'
    ' data-pjx-graph-panel data-open="false">'
    '<header class="pjx-graph__panel-head" data-pjx-graph-panel-head>'
    '<button type="button" class="pjx-graph__panel-control"'
    ' data-pjx-graph-panel-back aria-label="Back" hidden>Back</button>'
    '<h2 class="pjx-graph__panel-title" data-pjx-graph-panel-title></h2>'
    '<button type="button" class="pjx-graph__panel-control"'
    ' data-pjx-graph-panel-close aria-label="Close">Close</button>'
    "</header>"
    '<div class="pjx-graph__panel-content" data-pjx-graph-panel-content></div>'
    "</aside>"
)


def _html(session, **kwargs) -> str:
    return render(PJXGraphSidePanel(id="p", **kwargs), session)


def _root(parse_html, html):
    (root,) = parse_html(html)
    return root


class TestFields:
    def test_defaults(self):
        panel = PJXGraphSidePanel()
        assert panel.title == ""
        assert panel.aria_label == "Graph panel"
        assert panel.marker is False
        assert panel.accent_color == ""
        assert panel.badge == ""
        assert panel.back_label == "Back"
        assert panel.close_label == "Close"
        assert panel.open is False
        assert panel.content == ""
        assert panel.class_name == ""
        assert panel.extra_attrs == {}

    def test_class_name_rejects_double_quote(self):
        with pytest.raises(ValidationError):
            PJXGraphSidePanel(class_name='a"b')

    def test_accent_color_rejects_semicolon_and_quote(self):
        with pytest.raises(ValidationError, match="';'"):
            PJXGraphSidePanel(accent_color="red; display:none")
        with pytest.raises(ValidationError):
            PJXGraphSidePanel(accent_color='a"b')

    def test_extra_attrs_reject_both_quote_kinds_and_invalid_name(self):
        with pytest.raises(ValidationError):
            PJXGraphSidePanel(extra_attrs={"data-x": "a\"b'c"})
        with pytest.raises(ValidationError):
            PJXGraphSidePanel(extra_attrs={"bad name": "x"})


class TestMarkup:
    def test_dom_contract_closed(self, session):
        assert _html(session) == CLOSED

    def test_open_sets_data_open_true_and_nothing_else(self, session):
        assert _html(session, open=True) == CLOSED.replace(
            'data-open="false"', 'data-open="true"'
        )

    def test_single_root(self, session, parse_html):
        root = _root(parse_html, _html(session))
        assert root.tag == "aside"
        assert root.attrs["id"] == "p"
        assert root.attrs["aria-label"] == "Graph panel"
        assert root.classes == ["pjx-graph__panel"]
        assert "data-pjx-graph-panel" in root.attrs
        assert root.attrs["data-open"] == "false"
        head, content = root.children
        assert head.tag == "header"
        assert head.classes == ["pjx-graph__panel-head"]
        assert "data-pjx-graph-panel-head" in head.attrs
        assert content.tag == "div"
        assert content.classes == ["pjx-graph__panel-content"]
        assert "data-pjx-graph-panel-content" in content.attrs

    def test_header_order_without_optionals(self, session, parse_html):
        (head, _) = _root(parse_html, _html(session)).children
        back, title, close = head.children
        assert back.tag == "button"
        assert back.attrs["type"] == "button"
        assert back.classes == ["pjx-graph__panel-control"]
        assert "data-pjx-graph-panel-back" in back.attrs
        assert "hidden" in back.attrs
        assert title.tag == "h2"
        assert title.classes == ["pjx-graph__panel-title"]
        assert "data-pjx-graph-panel-title" in title.attrs
        assert close.tag == "button"
        assert close.attrs["type"] == "button"
        assert close.classes == ["pjx-graph__panel-control"]
        assert "data-pjx-graph-panel-close" in close.attrs
        assert "hidden" not in close.attrs

    def test_id_autogenerates(self, session, parse_html):
        root = _root(parse_html, render(PJXGraphSidePanel(), session))
        assert root.attrs["id"]

    def test_marker_renders_between_back_and_title(self, session, parse_html):
        (head, _) = _root(parse_html, _html(session, marker=True)).children
        back, marker, title, close = head.children
        assert "data-pjx-graph-panel-back" in back.attrs
        assert marker.tag == "span"
        assert marker.classes == ["pjx-graph__panel-marker"]
        assert "data-pjx-graph-panel-marker" in marker.attrs
        assert marker.attrs["aria-hidden"] == "true"
        assert marker.children == []
        assert "data-pjx-graph-panel-title" in title.attrs
        assert "data-pjx-graph-panel-close" in close.attrs

    def test_accent_color_sets_inline_token(self, session, parse_html):
        html = _html(session, accent_color="#f00")
        assert ' data-open="false" style="--pjx-graph-panel-accent: #f00">' in html
        assert _root(parse_html, html).attrs["style"] == (
            "--pjx-graph-panel-accent: #f00"
        )
        assert "style=" not in _html(session)
        assert "style=" not in _html(session, marker=True)

    def test_badge_slot_renders_raw_after_title(self, session, parse_html):
        (head, _) = _root(parse_html, _html(session, badge="<b>3</b>")).children
        _, title, badge, close = head.children
        assert "data-pjx-graph-panel-title" in title.attrs
        assert badge.tag == "span"
        assert badge.classes == ["pjx-graph__panel-badge"]
        assert "data-pjx-graph-panel-badge" in badge.attrs
        (bold,) = badge.children
        assert bold.tag == "b"
        assert "data-pjx-graph-panel-close" in close.attrs
        assert "data-pjx-graph-panel-badge" not in _html(session)

    def test_content_renders_raw_open_and_closed(self, session, parse_html):
        for is_open in (False, True):
            html = _html(session, content="<p>x</p>", open=is_open)
            (_, content) = _root(parse_html, html).children
            (paragraph,) = content.children
            assert paragraph.tag == "p"

    def test_component_values_fill_badge_and_content(self, session, parse_html):
        html = _html(
            session,
            badge=PJXGraphControls(id="k1"),
            content=PJXGraphControls(id="k2"),
        )
        head, content = _root(parse_html, html).children
        (_, _, badge, _) = head.children
        (in_badge,) = badge.children
        assert in_badge.attrs["id"] == "k1"
        assert in_badge.classes == ["pjx-graph__controls"]
        (in_content,) = content.children
        assert in_content.attrs["id"] == "k2"
        assert in_content.classes == ["pjx-graph__controls"]

    def test_tag_body_targets_content_not_badge(self):
        assert _resolve_children_field(PJXGraphSidePanel) == "content"

    def test_text_props_are_escaped(self, session, parse_html):
        text = '<b>&"x'
        escaped = "&lt;b&gt;&amp;&#34;x"
        html = _html(
            session,
            title=text,
            aria_label=text,
            back_label=text,
            close_label=text,
        )
        assert "<b>" not in html
        assert html.count(f'aria-label="{escaped}"') == 3
        assert f">{escaped}</h2>" in html
        assert html.count(f">{escaped}</button>") == 2
        root = _root(parse_html, html)
        assert all(el.tag != "b" for el in root.descendants())
        assert root.attrs["aria-label"] == text
        (head, _) = root.children
        back, _, close = head.children
        assert back.attrs["aria-label"] == text
        assert close.attrs["aria-label"] == text

    def test_label_props_replace_text_and_aria_label(self, session, parse_html):
        html = _html(session, back_label="Previous", close_label="Dismiss")
        assert ">Previous</button>" in html
        assert ">Dismiss</button>" in html
        (head, _) = _root(parse_html, html).children
        back, _, close = head.children
        assert back.attrs["aria-label"] == "Previous"
        assert close.attrs["aria-label"] == "Dismiss"

    def test_class_name_appends(self, session, parse_html):
        root = _root(parse_html, _html(session, class_name="extra more"))
        assert root.classes == ["pjx-graph__panel", "extra", "more"]
        assert 'class="pjx-graph__panel k&lt;&amp;"' in _html(session, class_name="k<&")

    def test_extra_attrs_on_root_escaped(self, session, parse_html):
        attrs = {"hx-swap-oob": "true", "data-k": "<y>&"}
        html = _html(session, extra_attrs=attrs)
        assert ' data-open="false" hx-swap-oob="true" data-k="&lt;y&gt;&amp;">' in html
        styled = _html(session, accent_color="#f00", extra_attrs=attrs)
        assert (
            ' style="--pjx-graph-panel-accent: #f00" hx-swap-oob="true"'
            ' data-k="&lt;y&gt;&amp;">' in styled
        )
        root = _root(parse_html, html)
        assert root.attrs["hx-swap-oob"] == "true"
        assert root.attrs["data-k"] == "<y>&"
        assert all("hx-swap-oob" not in el.attrs for el in root.descendants())

    def test_accent_color_is_escaped(self, session):
        assert 'style="--pjx-graph-panel-accent: a&lt;&amp;"' in _html(
            session, accent_color="a<&"
        )

    def test_renders_as_the_stage_last_child_beside_the_canvas(
        self, session, parse_html
    ):
        graph = PJXGraph(
            id="g",
            nodes=PJXGraphNodes(id="layer"),
            panel=PJXGraphSidePanel(id="p"),
        )
        root = _root(parse_html, render(graph, session))
        canvas, panel = root.children
        assert canvas.classes == ["pjx-graph__canvas"]
        assert panel.tag == "aside"
        assert panel.attrs["id"] == "p"
        assert all(el.tag != "aside" for el in canvas.descendants())


def _rule_block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"no rule for {selector}"
    return match.group(1)


class TestStylesheet:
    def test_css_asset_skeleton(self):
        css = CSS.read_text(encoding="utf-8")
        tokens = _rule_block(css, ":where(:root)")
        for token in (
            "--pjx-graph-panel-bg: var(--surface);",
            "--pjx-graph-panel-border: var(--border);",
            "--pjx-graph-panel-radius: var(--radius-md);",
            "--pjx-graph-panel-color: var(--text);",
            "--pjx-graph-panel-muted: var(--text-muted);",
            "--pjx-graph-panel-accent: var(--text-muted);",
            "--pjx-graph-panel-inset:",
            "--pjx-graph-panel-width:",
            "--pjx-graph-panel-gap:",
            "--pjx-graph-panel-duration:",
        ):
            assert token in tokens
        panel = _rule_block(css, ".pjx-graph__panel")
        assert "position: absolute" in panel
        assert "top: var(--pjx-graph-panel-inset)" in panel
        assert "right: var(--pjx-graph-panel-inset)" in panel
        assert "z-index:" in panel
        assert "width: var(--pjx-graph-panel-width)" in panel
        assert "max-height:" in panel
        closed = _rule_block(css, '.pjx-graph__panel[data-open="false"]')
        assert "display: none" in closed
        opened = _rule_block(css, '.pjx-graph__panel[data-open="true"]')
        assert "animation:" in opened
        assert "var(--pjx-graph-panel-duration)" in opened
        hidden = _rule_block(css, ".pjx-graph__panel-control[hidden]")
        assert "display: none" in hidden
        for selector in (
            ".pjx-graph__panel-head",
            ".pjx-graph__panel-control",
            ".pjx-graph__panel-marker",
            ".pjx-graph__panel-title",
            ".pjx-graph__panel-content",
        ):
            _rule_block(css, selector)
        assert "!important" not in css
        assert "pjx-icon" not in css

    def test_reduced_motion_clamps_open_animation(self):
        css = CSS.read_text(encoding="utf-8")
        start = css.index("@media (prefers-reduced-motion: reduce)")
        media = css[start:]
        rule = _rule_block(media, '.pjx-graph__panel[data-open="true"]')
        assert "animation-duration:" in rule
        assert "animation: none" not in media

    def test_rendering_registers_stylesheet(self, session):
        from pyjinhx.session import accumulate_assets

        assert PJXGraphSidePanel.__pjx_descriptor__.css_paths == (CSS,)
        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert CSS in session.css_assets
