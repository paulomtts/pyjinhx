"""PJXRosterPicker — the picker shell: search combobox, chips, cap hint, validity input and CSS."""

import pytest
from pydantic import ValidationError

from pyjinhx._component import _is_slot_field
from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem, PJXRosterPicker

TEXT_FIELDS = [
    "name",
    "candidates_url",
    "placeholder",
    "remove_label",
    "limit_label",
    "empty_message",
    "class_name",
]


def _items(*values):
    return [PJXRosterItem(value=value, label=value.upper()) for value in values]


# ── Props and validation ─────────────────────────────────────────────────────


def test_required_fields_only_gives_the_documented_defaults():
    picker = PJXRosterPicker(name="members", candidates_url="/people")

    assert picker.name == "members"
    assert picker.candidates_url == "/people"
    assert picker.items == []
    assert picker.max_items == 0
    assert picker.required is False
    assert picker.disabled is False
    assert picker.portal is False
    assert picker.placeholder == "Search…"
    assert picker.remove_label == "Remove"
    assert picker.limit_label == "Limit reached"
    assert picker.empty_message == "No results"
    assert picker.class_name == ""
    assert picker.extra_attrs == {}
    assert picker.chips == []


@pytest.mark.parametrize("field", ["name", "candidates_url"])
def test_missing_name_or_candidates_url_raises_naming_the_field(field):
    kwargs = {"name": "members", "candidates_url": "/people"}
    del kwargs[field]

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("field", ["name", "candidates_url"])
def test_empty_name_or_candidates_url_raises_naming_the_field(field):
    kwargs = {"name": "members", "candidates_url": "/people", field: ""}

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (field,)


def test_negative_max_items_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(name="members", candidates_url="/people", max_items=-1)

    assert exc_info.value.errors()[0]["loc"] == ("max_items",)


def test_duplicate_item_values_raise_naming_the_value():
    items = [
        PJXRosterItem(value="u1", label="Ada"),
        PJXRosterItem(value="u1", label="Bob"),
    ]

    with pytest.raises(ValidationError, match="'u1'"):
        PJXRosterPicker(name="members", candidates_url="/people", items=items)


def test_more_items_than_max_items_raises():
    with pytest.raises(ValidationError, match="max_items=2"):
        PJXRosterPicker(
            name="members",
            candidates_url="/people",
            items=_items("u1", "u2", "u3"),
            max_items=2,
        )


def test_items_equal_to_max_items_are_allowed():
    picker = PJXRosterPicker(
        name="members",
        candidates_url="/people",
        items=_items("u1", "u2"),
        max_items=2,
    )

    assert len(picker.chips) == 2


def test_zero_max_items_allows_any_count():
    picker = PJXRosterPicker(
        name="members",
        candidates_url="/people",
        items=_items(*[f"u{n}" for n in range(20)]),
    )

    assert len(picker.chips) == 20


def test_item_color_with_a_double_quote_raises_at_construction():
    items = [PJXRosterItem(value="u1", label="Ada", color='red"')]

    with pytest.raises(ValidationError, match="color"):
        PJXRosterPicker(name="members", candidates_url="/people", items=items)


def test_class_name_with_a_double_quote_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(name="members", candidates_url="/people", class_name='a"b')

    assert exc_info.value.errors()[0]["loc"] == ("class_name",)


def test_extra_attrs_with_a_bad_name_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(
            name="members", candidates_url="/people", extra_attrs={"bad name": "x"}
        )

    assert exc_info.value.errors()[0]["loc"] == ("extra_attrs",)


def test_chips_is_a_slot_field():
    assert _is_slot_field(PJXRosterPicker, "chips")


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_props_are_not_slot_fields(field):
    assert not _is_slot_field(PJXRosterPicker, field)
