"""PJXRosterItem — the frozen data model behind one roster chip or result row."""

import subprocess
import sys

import pytest
from markupsafe import Markup
from pydantic import ValidationError

from pyjinhx._component import PjxSlot, _is_slot_field
from pyjinhx.builtins.ui.pjx_roster_picker.item import PJXRosterItem

OPTIONAL_FIELDS = ["subtitle", "initials", "color", "src", "icon", "extra", "detail"]
TEXT_FIELDS = ["value", "label", "subtitle", "initials", "color", "src", "icon"]


def test_required_fields_only_defaults_every_optional_field_to_empty():
    item = PJXRosterItem(value="u1", label="Ada")

    assert item.value == "u1"
    assert item.label == "Ada"
    for name in OPTIONAL_FIELDS:
        assert getattr(item, name) == "", name


def test_every_field_is_stored_as_given():
    item = PJXRosterItem(
        value="u1",
        label="Ada <Lovelace>",
        subtitle="ada@example.com",
        initials="AL",
        color="#ff0000",
        src="/avatars/ada.png",
        icon="user",
        extra=Markup("<b>x</b>"),
        detail="<i>admin</i>",
    )

    assert item.value == "u1"
    assert item.label == "Ada <Lovelace>"
    assert item.subtitle == "ada@example.com"
    assert item.initials == "AL"
    assert item.color == "#ff0000"
    assert item.src == "/avatars/ada.png"
    assert item.icon == "user"
    # Pydantic coerces Markup to str, so compare text, not type.
    assert item.extra == "<b>x</b>"
    assert item.detail == "<i>admin</i>"


@pytest.mark.parametrize("missing", ["value", "label"])
def test_missing_value_or_label_raises(missing):
    kwargs = {"value": "u1", "label": "Ada"}
    del kwargs[missing]

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterItem(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (missing,)


@pytest.mark.parametrize("empty", ["value", "label"])
def test_empty_value_or_label_raises_naming_the_field(empty):
    kwargs = {"value": "u1", "label": "Ada", empty: ""}

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterItem(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (empty,)


def test_whitespace_value_is_accepted():
    item = PJXRosterItem(value=" ", label=" ")

    assert item.value == " "
    assert item.label == " "


@pytest.mark.parametrize("field", ["value", "label", "extra"])
def test_assigning_a_field_raises(field):
    item = PJXRosterItem(value="u1", label="Ada")

    with pytest.raises(ValidationError) as exc_info:
        setattr(item, field, "x")

    assert exc_info.value.errors()[0]["type"] == "frozen_instance"


def test_items_are_hashable_and_compare_by_value():
    a = PJXRosterItem(value="u1", label="Ada", extra=Markup("<b>x</b>"))
    b = PJXRosterItem(value="u1", label="Ada", extra="<b>x</b>")
    c = PJXRosterItem(value="u2", label="Ada")

    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert len({a, b, c}) == 2


@pytest.mark.parametrize("field", ["extra", "detail"])
def test_extra_and_detail_are_slot_fields(field):
    metadata = PJXRosterItem.model_fields[field].metadata

    assert any(isinstance(marker, PjxSlot) for marker in metadata)
    assert _is_slot_field(PJXRosterItem, field)


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_fields_are_not_slot_fields(field):
    assert not _is_slot_field(PJXRosterItem, field)


def test_item_module_imports_in_a_fresh_interpreter():
    # Builds the model on a clean sys.modules, where the Slot annotation's
    # BaseComponent reference must resolve without help from other imports.
    code = (
        "from pyjinhx.builtins.ui.pjx_roster_picker.item import PJXRosterItem\n"
        "assert PJXRosterItem(value='u1', label='Ada').extra == ''\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
