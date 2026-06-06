from enum import Enum
from typing import ClassVar

from pyjinhx import ReactiveComponent
from pyjinhx.cache import clear
from pyjinhx.utils import coerce_load_key, coerce_load_key_str, interpolate_reactive_keys


def test_singleton_keys_pass_through():
    assert interpolate_reactive_keys({"todos"}, None) == {"todos"}


def test_keyed_single_stem_expands():
    assert interpolate_reactive_keys({"todo"}, "42", keyed=True) == {"todo:42"}


def test_keyed_plural_sibling_splits_instance_and_collection():
    assert interpolate_reactive_keys({"user", "users"}, "2", keyed=True) == {
        "user:2",
        "users",
    }


def test_legacy_key_placeholder_still_works():
    assert interpolate_reactive_keys({"todo:{key}"}, "7", keyed=True) == {"todo:7"}


class TodoId(Enum):
    FIRST = 1
    SECOND = 2


class EnumRow(ReactiveComponent):
    label: str = ""
    reacts_to: ClassVar[set[str]] = {"row"}

    @classmethod
    def load(cls, key: str | int) -> "EnumRow":
        return cls(label=f"row {key}")


def test_coerce_load_key_unwraps_enum():
    assert coerce_load_key(TodoId.FIRST) == 1
    assert coerce_load_key_str(TodoId.SECOND) == "2"
    assert coerce_load_key("plain") == "plain"


def test_load_coerces_enum_to_value():
    clear()
    row = EnumRow.load(TodoId.FIRST)
    assert row.label == "row 1"
    assert row._pjx_key == "1"
    assert row.id == "enum-row-1"
