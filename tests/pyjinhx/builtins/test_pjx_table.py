"""PJXTable — v0.x output parity on the v2 engine."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_table import PJXTable
from pyjinhx.builtins.pjx_table_body import PJXTableBody
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    return RenderSession()


class TestFields:
    def test_defaults(self):
        table = PJXTable(id="t1")
        assert table.class_name == ""
        assert table.content == ""
        assert table.caption == ""
        assert table.striped is False
        assert table.sticky_header is False
        assert table.density == "comfortable"
        assert table.bordered == "none"
        assert table.extra_attrs == {}

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXTable.__pjx_descriptor__.slot_fields

    def test_content_is_the_children_field(self):
        assert PJXTable.__pjx_descriptor__.children_field == "content"


class TestRender:
    def test_bare_table(self, session):
        assert (
            render(PJXTable(id="t1"), session)
            == '<table id="t1" class="pjx-table"></table>'
        )

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"striped": True}, "pjx-table pjx-table--striped"),
            ({"sticky_header": True}, "pjx-table pjx-table--sticky"),
            ({"density": "compact"}, "pjx-table pjx-table--density-compact"),
            ({"density": "comfortable"}, "pjx-table"),
            ({"bordered": "horizontal"}, "pjx-table pjx-table--bordered-horizontal"),
            ({"bordered": "all"}, "pjx-table pjx-table--bordered-all"),
            ({"bordered": "none"}, "pjx-table"),
            ({"class_name": "wide"}, "pjx-table wide"),
        ],
    )
    def test_modifier_classes(self, session, kwargs, expected):
        assert f'class="{expected}"' in render(PJXTable(id="t1", **kwargs), session)

    def test_caption_is_emitted_before_content(self, session):
        assert render(PJXTable(id="t1", caption="Sales", content="x"), session) == (
            '<table id="t1" class="pjx-table">'
            '<caption class="pjx-table__caption">Sales</caption>x</table>'
        )

    def test_extra_attrs_surface_on_the_root(self, session):
        html = render(PJXTable(id="t1", extra_attrs={"data-sort": "asc"}), session)
        assert 'data-sort="asc"' in html[: html.index(">")]

    def test_no_caption_element_when_caption_is_empty(self, session):
        assert "<caption" not in render(PJXTable(id="t1"), session)

    def test_component_content_renders_nested(self, session):
        assert render(PJXTable(id="t1", content=PJXTableBody(id="b1")), session) == (
            '<table id="t1" class="pjx-table">'
            '<tbody id="b1" class="pjx-table__body"></tbody></table>'
        )


class TestValidation:
    @pytest.mark.parametrize("field, bad", [("density", "roomy"), ("bordered", "some")])
    def test_unknown_literal_raises(self, field, bad):
        with pytest.raises(ValidationError):
            PJXTable(id="t1", **{field: bad})


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXTable.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_table.css"
        assert css[0].is_file()

    def test_subcomponents_ship_no_stylesheet_of_their_own(self):
        assert PJXTableBody.__pjx_descriptor__.css_paths == ()


class TestSlotOpacity:
    def test_string_filter_on_a_component_slot_raises(self, session, tmp_path):
        """A component-valued slot is opaque: it is not a string to filter.

        Confirmed against pyjinhx/markers.py (ComponentNode.__str__ ->
        _opaque_error("str()") -> TypeError): `|striptags` stringifies its
        argument before doing its work, reaches ComponentNode.__str__, and
        raises TypeError.
        """
        template = tmp_path / "bad_slot.pjx"
        template.write_text(
            '<table id="{{ id }}" class="pjx-table">{{ content|striptags }}</table>'
        )
        env_session = RenderSession()

        class Probe(PJXTable):
            pass

        Probe.__pjx_descriptor__ = replace(
            PJXTable.__pjx_descriptor__, template_path=template
        )

        with pytest.raises(TypeError):
            render(Probe(id="t1", content=PJXTableBody(id="b1")), env_session)


class TestSingleRoot:
    def test_two_root_elements_raise(self, tmp_path):
        template = tmp_path / "two_roots.pjx"
        template.write_text('<table id="{{ id }}"></table><table></table>')

        class Probe(PJXTable):
            pass

        Probe.__pjx_descriptor__ = replace(
            PJXTable.__pjx_descriptor__, template_path=template
        )

        with pytest.raises(ValueError):
            render(Probe(id="t1"), RenderSession())
