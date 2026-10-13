"""PJXGraphSidePanel — the graph's floating side panel: fields, DOM contract, escaping, CSS."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_graph_side_panel import PJXGraphSidePanel
from pyjinhx.rendering import render

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
