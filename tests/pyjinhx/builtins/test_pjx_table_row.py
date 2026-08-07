"""PJXTableRow — v0.x output parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_table_row import PJXTableRow
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    return RenderSession()


class TestFields:
    def test_defaults(self):
        row = PJXTableRow(id="r1")
        assert row.class_name == ""
        assert row.content == ""
        assert row.selectable is False
        assert row.value == ""
        assert row.select_label == "Select row"
        assert row.extra_attrs == {}

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXTableRow.__pjx_descriptor__.slot_fields

    def test_content_is_the_children_field(self):
        assert PJXTableRow.__pjx_descriptor__.children_field == "content"


class TestRender:
    def test_bare_row_matches_v0(self, session):
        assert (
            render(PJXTableRow(id="r1"), session)
            == '<tr id="r1" class="pjx-table__row"></tr>'
        )

    def test_class_name_is_appended(self, session):
        assert (
            render(PJXTableRow(id="r1", class_name="hot"), session)
            == '<tr id="r1" class="pjx-table__row hot"></tr>'
        )

    def test_extra_attrs_surface_on_the_root(self, session):
        html = render(PJXTableRow(id="r1", extra_attrs={"data-id": "7"}), session)
        assert 'data-id="7"' in html[: html.index(">")]


class TestSelectable:
    def test_plain_row(self, session):
        assert (
            render(PJXTableRow(id="r1", content="x"), session)
            == '<tr id="r1" class="pjx-table__row">x</tr>'
        )

    def test_selectable_prepends_a_checkbox_cell(self, session):
        assert render(PJXTableRow(id="r1", selectable=True, value="7"), session) == (
            '<tr id="r1" class="pjx-table__row pjx-table__row--selectable">'
            '<td class="pjx-table__select">'
            '<input type="checkbox" name="selected" value="7" aria-label="Select row">'
            "</td></tr>"
        )

    def test_select_label_is_overridable_and_escaped(self, session):
        # Confirmed against MarkupSafe's autoescape output: `"` -> `&#34;`.
        html = render(
            PJXTableRow(id="r1", selectable=True, value="7", select_label='pick "me"'),
            session,
        )
        assert 'aria-label="pick &#34;me&#34;"' in html

    def test_selectable_rejects_a_non_bool(self):
        with pytest.raises(ValidationError):
            PJXTableRow(id="r1", selectable="maybe")  # type: ignore[arg-type]
