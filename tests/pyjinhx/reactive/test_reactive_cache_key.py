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


def test_protocol_mode_string_key_is_hashed_once_the_plain_form_is_long():
    class Row(ReactiveComponent):
        model_config = ConfigDict(extra="allow")
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int, payload: str = "") -> "Row":
            return cls(row_id=row_id, payload=payload)  # type: ignore[reportCallIssue]

    long_payload = "x" * 512
    prefix = f"pjx:1:{Row.__module__}.{Row.__qualname__}:"

    first = _string_cache_key(
        Row, {"row_id": 1, "payload": long_payload}, protocol_mode=True
    )
    again = _string_cache_key(
        Row, {"row_id": 1, "payload": long_payload}, protocol_mode=True
    )
    different = _string_cache_key(
        Row, {"row_id": 1, "payload": "y" * 512}, protocol_mode=True
    )

    digest = first.removeprefix(prefix)
    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)
    assert long_payload not in first
    assert first == again
    assert first != different


def test_protocol_mode_string_key_below_the_threshold_stays_plain():
    class Row(ReactiveComponent):
        model_config = ConfigDict(extra="allow")
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    key = _string_cache_key(Row, {"row_id": 1}, protocol_mode=True)

    assert key == f"pjx:1:{Row.__module__}.{Row.__qualname__}:row_id=1"


def test_protocol_mode_class_with_an_unserializable_load_param_is_rejected():
    class Opaque:
        pass

    with pytest.raises(TypeError, match="serialize deterministically"):

        class Row(ReactiveComponent):
            model_config = ConfigDict(extra="allow")
            row_id: Annotated[int, PjxKey()] = 0

            @classmethod
            def load(cls, row_id: int, blob: Opaque) -> "Row":
                return cls(row_id=row_id)


def test_protocol_mode_class_with_an_unannotated_load_param_is_rejected():
    with pytest.raises(TypeError, match="serialize deterministically"):

        class Row(ReactiveComponent):
            model_config = ConfigDict(extra="allow")
            row_id: Annotated[int, PjxKey()] = 0

            @classmethod
            def load(cls, row_id: int, flavor=None) -> "Row":  # type: ignore[no-untyped-def]
                return cls(row_id=row_id)


def test_strict_mode_classes_are_exempt_from_the_determinism_check():
    # `object` stands in for a "risky" type here rather than a custom class:
    # a custom arbitrary type would also need arbitrary_types_allowed=True on
    # the model itself for the PjxKey field to validate at all, which is an
    # orthogonal pydantic concern this test isn't about. `object` is a valid
    # pydantic field type out of the box and is explicitly on the spec's
    # rejected list for protocol mode, so it still exercises "risky type,
    # strict mode, must not raise".
    class Row(ReactiveComponent):
        blob: Annotated[object, PjxKey()] = "unset"

        @classmethod
        def load(cls, blob: object) -> "Row":
            return cls(blob=blob)

    assert Row._pjx_key_field == "blob"


def test_protocol_mode_class_with_serializable_load_params_defines_cleanly():
    class Row(ReactiveComponent):
        model_config = ConfigDict(extra="allow")
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(
            cls,
            row_id: int,
            flavor: str = "plain",
            ratio: float = 1.0,
            on: bool = True,
            note: str | None = None,
            tags: tuple[str, ...] = (),
        ) -> "Row":
            return cls(row_id=row_id)

    assert Row.load(1) is not None  # class defined and the wrap installed
