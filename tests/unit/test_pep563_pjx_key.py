"""PjxKey detection must survive PEP 563 string annotations (issue #67, finding 1)."""

from __future__ import annotations

from typing import Annotated

import pytest

from pyjinhx import MutationKey, PjxKey, ReactiveComponent


class Keys(MutationKey):
    ROW = "row"


class FutureRow(ReactiveComponent, react={Keys.ROW}):
    row_key: Annotated[str, PjxKey()]
    label: str = ""

    @classmethod
    def load(cls, key: str) -> FutureRow:
        return cls(row_key=str(key), label=f"row {key}")


def test_pep563_class_definition_detects_pjx_key():
    assert FutureRow._pjx_keyed is True
    assert FutureRow._pjx_load_field == "row_key"


def test_pep563_load_and_render():
    row = FutureRow.load("7")
    assert row.row_key == "7"
    html = str(row._render(source="<div>{{ label }}</div>"))
    assert 'data-pjx-load="7"' in html
    assert "row 7" in html


def test_pep563_subclass_inherits_single_pjx_key_field():
    class ChildRow(FutureRow, react={Keys.ROW}):
        @classmethod
        def load(cls, key: str) -> ChildRow:
            return cls(row_key=str(key), label=f"child {key}")

    assert ChildRow._pjx_load_field == "row_key"


def test_pep563_keyed_load_without_pjx_key_still_raises():
    with pytest.raises(TypeError, match="declare exactly"):

        class Missing(ReactiveComponent, react={Keys.ROW}):
            row_key: str

            @classmethod
            def load(cls, key: str) -> Missing:
                return cls(row_key=str(key))


def test_pep563_multiple_pjx_key_fields_still_raise():
    with pytest.raises(TypeError, match="declare exactly"):

        class Doubled(ReactiveComponent, react={Keys.ROW}):
            first: Annotated[str, PjxKey()]
            second: Annotated[str, PjxKey()]

            @classmethod
            def load(cls, key: str) -> Doubled:
                return cls(first=str(key), second=str(key))
