"""PJXTableBody — v0.x output parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_table_body import PJXTableBody
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    return RenderSession(template_dir="/")


class TestFields:
    def test_defaults(self):
        body = PJXTableBody(id="b1")
        assert body.class_name == ""
        assert body.content == ""

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXTableBody.__pjx_descriptor__.slot_fields

    def test_content_is_the_children_field(self):
        assert PJXTableBody.__pjx_descriptor__.children_field == "content"


class TestRender:
    def test_bare_body_matches_v0(self, session):
        assert (
            render(PJXTableBody(id="b1"), session)
            == '<tbody id="b1" class="pjx-table__body"></tbody>'
        )

    def test_class_name_is_appended(self, session):
        assert (
            render(PJXTableBody(id="b1", class_name="sticky"), session)
            == '<tbody id="b1" class="pjx-table__body sticky"></tbody>'
        )

    def test_string_content_stays_raw(self, session):
        # ADR 0003: a plain str in a Slot field is authored markup.
        assert (
            render(PJXTableBody(id="b1", content="a & b"), session)
            == '<tbody id="b1" class="pjx-table__body">a & b</tbody>'
        )

    def test_component_content_renders_as_an_opaque_child(self, session):
        from pyjinhx.builtins.pjx_table_cell import PJXTableCell

        outer = PJXTableBody(id="b1", content=PJXTableCell(id="c1", content="x"))
        assert render(outer, session) == (
            '<tbody id="b1" class="pjx-table__body">'
            '<td id="c1" class="pjx-table__cell">x</td>'
            "</tbody>"
        )


class TestValidation:
    def test_class_name_rejects_a_non_string(self):
        with pytest.raises(ValidationError):
            PJXTableBody(id="b1", class_name=object())  # type: ignore[arg-type]
