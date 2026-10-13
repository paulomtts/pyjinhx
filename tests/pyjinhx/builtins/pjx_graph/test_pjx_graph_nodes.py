"""PJXGraphNodes — the node layer of the graph builtin: fields, markup, join()."""

import pytest
from markupsafe import Markup
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_badge.pjx_badge import PJXBadge
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render


class TestFields:
    def test_defaults(self):
        layer = PJXGraphNodes(id="n")
        assert layer.nodes_html == ""
        assert layer.class_name == ""
        assert layer.extra_attrs == {}

    def test_class_name_rejects_double_quote(self):
        with pytest.raises(ValidationError):
            PJXGraphNodes(id="n", class_name='a"b')

    def test_extra_attrs_reject_both_quote_kinds(self):
        with pytest.raises(ValidationError):
            PJXGraphNodes(id="n", extra_attrs={"data-x": "a\"b'c"})

    def test_extra_attrs_reject_invalid_name(self):
        with pytest.raises(ValidationError):
            PJXGraphNodes(id="n", extra_attrs={"bad name": "x"})


class TestMarkup:
    def test_root_contract(self, session, parse_html):
        html = render(PJXGraphNodes(id="n"), session)
        assert html == '<div id="n" class="pjx-graph__nodes"></div>'
        (root,) = parse_html(html)
        assert root.tag == "div"
        assert root.attrs["id"] == "n"
        assert root.classes == ["pjx-graph__nodes"]
        assert root.children == []

    def test_nodes_html_renders_raw(self, session):
        html = render(PJXGraphNodes(id="n", nodes_html="<b>x</b><i>y</i>"), session)
        assert html == '<div id="n" class="pjx-graph__nodes"><b>x</b><i>y</i></div>'

    def test_class_name_appends(self, session, parse_html):
        html = render(PJXGraphNodes(id="n", class_name="extra more"), session)
        (root,) = parse_html(html)
        assert root.classes == ["pjx-graph__nodes", "extra", "more"]

    def test_class_name_escapes_angle_and_ampersand(self, session, parse_html):
        html = render(PJXGraphNodes(id="n", class_name="a<b&c"), session)
        assert 'class="pjx-graph__nodes a&lt;b&amp;c"' in html
        (root,) = parse_html(html)
        assert root.attrs["class"] == "pjx-graph__nodes a<b&c"

    def test_extra_attrs_on_root_escaped(self, session, parse_html):
        html = render(
            PJXGraphNodes(id="n", extra_attrs={"hx-get": "/n", "data-x": "<y>"}),
            session,
        )
        assert 'data-x="&lt;y&gt;"' in html
        (root,) = parse_html(html)
        assert root.attrs["hx-get"] == "/n"
        assert root.attrs["data-x"] == "<y>"


class TestJoin:
    def test_join_concatenates_rendered_markup(self, session, parse_html):
        a = render(PJXBadge(id="a", label="A"), session)
        b = render(PJXBadge(id="b", label="B"), session)
        joined = PJXGraphNodes.join([a, b])
        assert isinstance(joined, Markup)
        assert str(joined) == a + b
        assert "&lt;" not in joined

        html = render(PJXGraphNodes(id="n", nodes_html=joined), session)
        (root,) = parse_html(html)
        assert [child.attrs["id"] for child in root.children] == ["a", "b"]

    def test_join_of_nothing_is_empty_markup(self):
        joined = PJXGraphNodes.join([])
        assert isinstance(joined, Markup)
        assert joined == Markup("")

    def test_join_accepts_generator(self):
        joined = PJXGraphNodes.join(f"<i>{n}</i>" for n in range(3))
        assert str(joined) == "<i>0</i><i>1</i><i>2</i>"

    def test_join_keeps_markup_and_entities_verbatim(self):
        joined = PJXGraphNodes.join([Markup("<i>a</i>"), "<b>&amp;</b>"])
        assert str(joined) == "<i>a</i><b>&amp;</b>"


def test_exported_from_the_builtins_namespace():
    from pyjinhx import builtins

    assert "PJXGraphNodes" in builtins.__all__
    assert builtins.PJXGraphNodes is PJXGraphNodes
