"""PJXTableCell — v0.x output parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_table_cell import PJXTableCell
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # Descriptor template paths are absolute (module-dir walk in _component.py);
    # FileSystemLoader reconstructs them by joining the search root with the
    # split pieces, so the root "/" is the only search root that round-trips
    # an absolute path back to itself.
    return RenderSession()


class TestFields:
    def test_defaults(self):
        cell = PJXTableCell(id="c1")
        assert cell.class_name == ""
        assert cell.content == ""

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXTableCell.__pjx_descriptor__.slot_fields

    def test_content_is_the_children_field(self):
        assert PJXTableCell.__pjx_descriptor__.children_field == "content"


class TestRender:
    def test_bare_cell_matches_v0(self, session):
        assert (
            render(PJXTableCell(id="c1"), session)
            == '<td id="c1" class="pjx-table__cell"></td>'
        )

    def test_class_name_is_appended(self, session):
        assert (
            render(PJXTableCell(id="c1", class_name="num"), session)
            == '<td id="c1" class="pjx-table__cell num"></td>'
        )

    def test_string_content_stays_raw(self, session):
        # ADR 0003: a plain str in a Slot field is authored markup.
        assert (
            render(PJXTableCell(id="c1", content="a & b"), session)
            == '<td id="c1" class="pjx-table__cell">a & b</td>'
        )

    def test_component_content_renders_as_an_opaque_child(self, session):
        # A component nested directly inside an instance of its own class trips
        # render.py's same-class cycle guard (ADR 0004), which is correct
        # engine behavior, not a bug to work around — so opacity is exercised
        # with a distinct subclass instead of a second PJXTableCell.
        class InnerCell(PJXTableCell):
            pass

        outer = PJXTableCell(id="c1", content=InnerCell(id="c2", content="x"))
        assert render(outer, session) == (
            '<td id="c1" class="pjx-table__cell">'
            '<td id="c2" class="pjx-table__cell">x</td>'
            "</td>"
        )


class TestValidation:
    def test_class_name_rejects_a_non_string(self):
        with pytest.raises(ValidationError):
            PJXTableCell(id="c1", class_name=object())  # type: ignore[arg-type]
