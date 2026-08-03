"""PJXTableHead — v0.x output parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_table_head import PJXTableHead
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    return RenderSession(template_dir="/")


class TestFields:
    def test_defaults(self):
        head = PJXTableHead(id="h1")
        assert head.class_name == ""
        assert head.content == ""

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXTableHead.__pjx_descriptor__.slot_fields

    def test_content_is_the_children_field(self):
        assert PJXTableHead.__pjx_descriptor__.children_field == "content"


class TestRender:
    def test_bare_head_matches_v0(self, session):
        assert (
            render(PJXTableHead(id="h1"), session)
            == '<thead id="h1" class="pjx-table__head"></thead>'
        )

    def test_class_name_is_appended(self, session):
        assert (
            render(PJXTableHead(id="h1", class_name="sticky"), session)
            == '<thead id="h1" class="pjx-table__head sticky"></thead>'
        )

    def test_string_content_stays_raw(self, session):
        # ADR 0003: a plain str in a Slot field is authored markup.
        assert (
            render(PJXTableHead(id="h1", content="a & b"), session)
            == '<thead id="h1" class="pjx-table__head">a & b</thead>'
        )

    def test_component_content_renders_as_an_opaque_child(self, session):
        from pyjinhx.builtins.pjx_table_cell import PJXTableCell

        outer = PJXTableHead(id="h1", content=PJXTableCell(id="c1", content="x"))
        assert render(outer, session) == (
            '<thead id="h1" class="pjx-table__head">'
            '<td id="c1" class="pjx-table__cell">x</td>'
            "</thead>"
        )


class TestValidation:
    def test_class_name_rejects_a_non_string(self):
        with pytest.raises(ValidationError):
            PJXTableHead(id="h1", class_name=object())  # type: ignore[arg-type]
