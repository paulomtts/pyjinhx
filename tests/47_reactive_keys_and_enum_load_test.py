from enum import Enum
from typing import Annotated, ClassVar

from pyjinhx import PjxKey, ReactiveComponent
from pyjinhx.cache import LoadCache
from pyjinhx.reactive import oob_swaps
from pyjinhx.keys import (
    coerce_load_key_str,
    coerce_reactive_key,
    coerce_reactive_keys,
)


class MutationKey(str, Enum):
    TODOS = "todos"
    ROW = "row"


def test_coerce_reactive_key_unwraps_enum():
    assert coerce_reactive_key(MutationKey.TODOS) == "todos"
    assert coerce_reactive_keys({MutationKey.TODOS, "users"}) == {"todos", "users"}


class TodoId(Enum):
    FIRST = 1
    SECOND = 2


class EnumRow(ReactiveComponent):
    row_key: Annotated[str, PjxKey()]
    label: str = ""
    reacts_to: ClassVar[set[str | MutationKey]] = {MutationKey.ROW}

    @classmethod
    def load(cls, key: str) -> "EnumRow":
        return cls(row_key=str(key), label=f"row {key}")


def test_reacts_to_coerces_enums_at_class_definition():
    assert EnumRow._pjx_reacts_to == frozenset({"row"})


class TodoCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str | MutationKey]] = {MutationKey.TODOS}

    @classmethod
    def load(cls) -> "TodoCounter":
        return cls(remaining=0)


def test_reacts_to_enum_matches_string_dirtied_in_oob_swaps():
    LoadCache.clear()
    out = str(
        oob_swaps(
            {"todos"},
            [{"id": "counter", "type": "TodoCounter", "hash": "stale"}],
        )
    )
    assert "outerHTML:[data-pjx-id='counter']" in out


def test_dirtied_enum_matches_enum_reacts_to_in_oob_swaps():
    LoadCache.clear()
    out = str(
        oob_swaps(
            {MutationKey.TODOS},
            [{"id": "counter", "type": "TodoCounter", "hash": "stale"}],
        )
    )
    assert "outerHTML:[data-pjx-id='counter']" in out


def test_coerce_reactive_key_unwraps_todo_id_enum():
    assert coerce_reactive_key(TodoId.FIRST) == "1"
    assert coerce_load_key_str(TodoId.SECOND) == "2"
    assert coerce_reactive_key("plain") == "plain"
    assert coerce_reactive_key(42) == "42"


def test_load_coerces_enum_to_str_for_load():
    LoadCache.clear()
    row = EnumRow.load(TodoId.FIRST)
    assert row.label == "row 1"
    assert row._pjx_key == "1"
    assert row.id == "enum-row-1"
