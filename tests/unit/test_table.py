"""PJXTable and compound parts — structural wrappers + styling."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import (
    PJXTable, PJXTableHead, PJXTableBody, PJXTableRow, PJXTableHeaderCell, PJXTableCell,
)


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_table_root_element_and_class():
    html = str(PJXTable(id="t", content="x").render())
    assert "<table" in html and 'id="t"' in html
    assert 'class="pjx-table"' in html or 'class="pjx-table ' in html or 'class="pjx-table"' in html


def test_table_caption_rendered_only_when_set_and_escaped():
    assert "<caption" not in str(PJXTable(id="t", content="x").render())
    html = str(PJXTable(id="t", caption="A & B", content="x").render())
    assert '<caption class="pjx-table__caption">A &amp; B</caption>' in html


def test_table_modifier_classes():
    html = str(PJXTable(
        id="t", striped=True, sticky_header=True, density="compact", bordered="all", content="x"
    ).render())
    for mod in ("pjx-table--striped", "pjx-table--sticky",
                "pjx-table--density-compact", "pjx-table--bordered-all"):
        assert mod in html


def test_table_bordered_horizontal_and_defaults_add_no_class():
    h = str(PJXTable(id="t", bordered="horizontal", content="x").render())
    assert "pjx-table--bordered-horizontal" in h
    d = str(PJXTable(id="t", content="x").render())  # all defaults
    # Strip the inlined <style> block so we only check the HTML element classes.
    import re as _re
    d_html = _re.sub(r"<style[^>]*>.*?</style>", "", d, flags=_re.DOTALL)
    for mod in ("--striped", "--sticky", "--density-compact", "--bordered"):
        assert mod not in d_html


def test_head_body_row_cell_elements():
    assert "<thead" in str(PJXTableHead(id="h", content="x").render())
    assert "<tbody" in str(PJXTableBody(id="b", content="x").render())
    assert "<tr" in str(PJXTableRow(id="r", content="x").render())
    assert "<td" in str(PJXTableCell(id="c", content="x").render())


def test_header_cell_is_th_with_scope_col():
    html = str(PJXTableHeaderCell(id="hc", content="Name").render())
    assert "<th" in html and 'scope="col"' in html
    assert "pjx-table__th" in html
    assert "Name" in html


def test_class_name_appends_on_each_part():
    assert "mine" in str(PJXTableCell(id="c", class_name="mine", content="x").render())
    assert "mine" in str(PJXTableRow(id="r", class_name="mine", content="x").render())


def test_header_cell_non_sortable_is_plain_th_no_button():
    html = str(PJXTableHeaderCell(id="hc", content="Name").render())
    assert "<button" not in html
    assert "aria-sort" not in html


def test_header_cell_sortable_renders_button_and_aria_sort_none():
    html = str(PJXTableHeaderCell(id="hc", sortable=True, content="Name").render())
    assert "pjx-table__th--sortable" in html
    assert 'aria-sort="none"' in html
    assert '<button type="button" class="pjx-table__sort">' in html
    assert '<span class="pjx-table__sort-caret" aria-hidden="true"></span>' in html
    assert "Name" in html


def test_header_cell_sort_direction_maps_to_aria_sort():
    asc = str(PJXTableHeaderCell(id="hc", sortable=True, sort="asc", content="N").render())
    assert 'aria-sort="ascending"' in asc
    desc = str(PJXTableHeaderCell(id="hc", sortable=True, sort="desc", content="N").render())
    assert 'aria-sort="descending"' in desc


def test_sort_without_sortable_is_inert():
    # sort set but sortable False → no aria-sort, no button (sortable is the gate)
    html = str(PJXTableHeaderCell(id="hc", sort="asc", content="N").render())
    assert "aria-sort" not in html and "<button" not in html


def test_row_non_selectable_has_no_checkbox_cell():
    html = str(PJXTableRow(id="r", content="<td>x</td>").render())
    assert "pjx-table__select" not in html and "checkbox" not in html


def test_row_selectable_prepends_checkbox_cell():
    html = str(PJXTableRow(id="r", selectable=True, value="42", content="<td>x</td>").render())
    assert "pjx-table__row--selectable" in html
    assert '<td class="pjx-table__select">' in html
    assert 'type="checkbox"' in html
    assert 'name="selected"' in html
    assert 'value="42"' in html
    assert 'aria-label="Select row"' in html
    # the checkbox cell comes before the authored content
    assert html.index("pjx-table__select") < html.index("<td>x</td>")


def test_row_select_label_override_and_value_escaped():
    html = str(PJXTableRow(id="r", selectable=True, value='a"b', select_label="Pick", content="").render())
    assert 'aria-label="Pick"' in html
    assert 'value="a"b"' not in html  # the raw unescaped form must not appear
    assert "a&#34;b" in html or "a&quot;b" in html  # escaped
