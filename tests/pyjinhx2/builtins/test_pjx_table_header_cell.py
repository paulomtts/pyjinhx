"""PJXTableHeaderCell — v0.x output parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.pjx_table_header_cell import PJXTableHeaderCell
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def session():
    return RenderSession(template_dir="/")


class TestFields:
    def test_defaults(self):
        cell = PJXTableHeaderCell(id="h1")
        assert cell.class_name == ""
        assert cell.content == ""
        assert cell.sortable is False
        assert cell.sort == "none"

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXTableHeaderCell.__pjx_descriptor__.slot_fields

    def test_content_is_the_children_field(self):
        assert PJXTableHeaderCell.__pjx_descriptor__.children_field == "content"


class TestSortable:
    def test_plain_header_cell(self, session):
        assert (
            render(PJXTableHeaderCell(id="h1", content="Name"), session)
            == '<th scope="col" id="h1" class="pjx-table__th">Name</th>'
        )

    def test_sortable_wraps_content_in_a_button(self, session):
        assert render(
            PJXTableHeaderCell(id="h1", sortable=True, content="Name"), session
        ) == (
            '<th scope="col" id="h1" class="pjx-table__th pjx-table__th--sortable"'
            ' aria-sort="none">'
            '<button type="button" class="pjx-table__sort">Name'
            '<span class="pjx-table__sort-caret" aria-hidden="true"></span>'
            "</button></th>"
        )

    @pytest.mark.parametrize(
        ("sort", "aria"), [("none", "none"), ("asc", "ascending"), ("desc", "descending")]
    )
    def test_aria_sort_mapping(self, session, sort, aria):
        html = render(
            PJXTableHeaderCell(id="h1", sortable=True, sort=sort, content="Name"), session
        )
        assert f'aria-sort="{aria}"' in html

    def test_sort_is_absent_when_not_sortable(self, session):
        assert "aria-sort" not in render(
            PJXTableHeaderCell(id="h1", sort="asc", content="Name"), session
        )

    def test_unknown_sort_value_raises(self):
        with pytest.raises(ValidationError):
            PJXTableHeaderCell(id="h1", sort="sideways")


class TestValidation:
    def test_class_name_rejects_a_non_string(self):
        with pytest.raises(ValidationError):
            PJXTableHeaderCell(id="h1", class_name=object())
