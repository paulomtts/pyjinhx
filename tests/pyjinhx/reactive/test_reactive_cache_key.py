"""The versioned string form of the load cache key (tier-2 key derivation)."""

from typing import Annotated

import pytest
from pydantic import ConfigDict

from pyjinhx.reactive.component import (
    PjxKey,
    ReactiveComponent,
    _string_cache_key,
)


def test_string_key_has_the_versioned_namespace_and_the_load_key():
    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    key = _string_cache_key(Row, {"row_id": 7}, protocol_mode=False)

    assert key == f"pjx:1:{Row.__module__}.{Row.__qualname__}:7"


def test_string_key_for_a_class_with_no_key_field_uses_the_placeholder_segment():
    class Widget(ReactiveComponent):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            return cls(value="loaded")

    key = _string_cache_key(Widget, {}, protocol_mode=False)

    assert key == f"pjx:1:{Widget.__module__}.{Widget.__qualname__}:-"
    assert not key.endswith(":None")


def test_string_key_keeps_a_falsy_real_load_key_distinct_from_the_no_key_placeholder():
    class Row(ReactiveComponent):
        row_id: Annotated[str, PjxKey()] = ""

        @classmethod
        def load(cls, row_id: str) -> "Row":
            return cls(row_id=row_id)

    empty_key = _string_cache_key(Row, {"row_id": ""}, protocol_mode=False)
    dash_key = _string_cache_key(Row, {"row_id": "-"}, protocol_mode=False)

    # An empty-string load key is a real, distinct value — it must not collapse
    # onto the same segment the "no PjxKey field at all" placeholder uses, and
    # it must not collide with a different instance whose real key IS "-".
    assert empty_key != dash_key
    assert empty_key == f"pjx:1:{Row.__module__}.{Row.__qualname__}:"
    assert dash_key == f"pjx:1:{Row.__module__}.{Row.__qualname__}:-"


def test_protocol_mode_string_key_is_insensitive_to_argument_order():
    class Row(ReactiveComponent):
        model_config = ConfigDict(extra="allow")
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int, flavor: str = "plain") -> "Row":
            return cls(row_id=row_id, flavor=flavor)  # type: ignore[reportCallIssue]

    first = _string_cache_key(
        Row, {"row_id": 1, "flavor": "spicy"}, protocol_mode=True
    )
    second = _string_cache_key(
        Row, {"flavor": "spicy", "row_id": 1}, protocol_mode=True
    )

    assert first == second


def test_protocol_mode_string_key_separates_calls_that_differ_in_any_argument():
    class Row(ReactiveComponent):
        model_config = ConfigDict(extra="allow")
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int, flavor: str = "plain") -> "Row":
            return cls(row_id=row_id, flavor=flavor)  # type: ignore[reportCallIssue]

    plain = _string_cache_key(Row, {"row_id": 1, "flavor": "plain"}, protocol_mode=True)
    spicy = _string_cache_key(Row, {"row_id": 1, "flavor": "spicy"}, protocol_mode=True)
    other = _string_cache_key(Row, {"row_id": 2, "flavor": "plain"}, protocol_mode=True)

    assert plain != spicy
    assert plain != other
