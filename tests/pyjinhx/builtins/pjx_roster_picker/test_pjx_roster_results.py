"""PJXRosterResults — one page of roster picker search results."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx._component import _is_slot_field
from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults
from pyjinhx.rendering import render

PACKAGE_DIR = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_roster_results"
)
TEXT_FIELDS = [
    "picker_id",
    "next_url",
    "next_cursor",
    "empty_message",
    "remove_label",
]


def _items(*values):
    return [PJXRosterItem(value=value, label=value.upper()) for value in values]


def _results(parse_html, session, **kwargs):
    """Render one results page (picker_id defaults to p1) and return its single root."""
    kwargs.setdefault("picker_id", "p1")
    roots = parse_html(render(PJXRosterResults(**kwargs), session))
    assert len(roots) == 1
    return roots[0]


def _by_class(root, name):
    return [el for el in root.descendants() if name in el.classes]


def _one(root, name):
    found = _by_class(root, name)
    assert len(found) == 1, name
    return found[0]


# ── Props and validation ─────────────────────────────────────────────────────


def test_required_fields_only_gives_the_documented_defaults():
    results = PJXRosterResults(picker_id="p1")

    assert results.picker_id == "p1"
    assert results.items == []
    assert results.next_url == ""
    assert results.next_cursor == ""
    assert results.empty_message == "No results"
    assert results.remove_label == "Remove"
    assert results.class_name == ""
    assert results.extra_attrs == {}


def test_missing_picker_id_raises_naming_the_field():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults()  # pyright: ignore[reportCallIssue]

    assert exc_info.value.errors()[0]["loc"] == ("picker_id",)


@pytest.mark.parametrize("picker_id", ["", "p 1", "p\t1", "p1\n"])
def test_empty_or_whitespace_picker_id_raises_naming_the_field(picker_id):
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults(picker_id=picker_id)

    assert exc_info.value.errors()[0]["loc"] == ("picker_id",)


def test_class_name_with_a_double_quote_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults(picker_id="p1", class_name='a"b')

    assert exc_info.value.errors()[0]["loc"] == ("class_name",)


def test_extra_attrs_with_a_bad_name_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults(picker_id="p1", extra_attrs={"bad name": "x"})

    assert exc_info.value.errors()[0]["loc"] == ("extra_attrs",)


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_props_are_not_slot_fields(field):
    assert not _is_slot_field(PJXRosterResults, field)


# ── Markup ───────────────────────────────────────────────────────────────────


def test_root_is_one_div_carrying_id_classes_marker_and_extra_attrs(
    parse_html, session
):
    root = _results(
        parse_html,
        session,
        id="page-1",
        class_name="mine",
        extra_attrs={"data-team": "core"},
    )

    assert root.tag == "div"
    assert root.attrs["id"] == "page-1"
    assert "pjx-roster-picker__results-page" in root.classes
    assert "mine" in root.classes
    assert "data-pjx-roster-results" in root.attrs
    assert root.attrs["data-team"] == "core"


def test_package_ships_no_css_or_js():
    assert PACKAGE_DIR.is_dir()
    assert list(PACKAGE_DIR.glob("*.css")) == []
    assert list(PACKAGE_DIR.glob("*.js")) == []
