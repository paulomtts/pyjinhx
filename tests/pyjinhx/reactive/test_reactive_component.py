"""ReactiveComponent: the load() wrap installed at class-definition time."""

from typing import Any

import pytest

from pyjinhx.component import BaseComponent
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.session import request_scope


def test_reactive_component_is_a_base_component():
    assert issubclass(ReactiveComponent, BaseComponent)


def test_defining_a_subclass_replaces_load_with_the_wrapper():
    def original(self: Any) -> str:
        return "value"

    Widget = type("Widget", (ReactiveComponent,), {"load": original})

    assert Widget.load is not original


def test_load_body_runs_once_per_request_scope():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        def load(self) -> str:
            calls.append(1)
            return "loaded"

    widget = Widget()
    with request_scope():
        assert widget.load() == "loaded"
        assert widget.load() == "loaded"

    assert len(calls) == 1


def test_a_cached_none_is_not_reloaded():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        def load(self) -> None:
            calls.append(1)
            return None  # noqa: RET501, PLR1711 -- explicit for readability of the assertion below

    widget = Widget()
    with request_scope():
        assert widget.load() is None
        assert widget.load() is None

    assert len(calls) == 1


def test_load_runs_every_call_outside_a_request_scope():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        def load(self) -> str:
            calls.append(1)
            return "loaded"

    widget = Widget()
    assert widget.load() == "loaded"
    assert widget.load() == "loaded"
    assert len(calls) == 2


def test_each_request_scope_starts_cold():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        def load(self) -> str:
            calls.append(1)
            return "loaded"

    widget = Widget()
    with request_scope():
        widget.load()
    with request_scope():
        widget.load()

    assert len(calls) == 2


def test_react_keys_are_forwarded_to_cache_put():
    from unittest.mock import patch

    class Widget(ReactiveComponent, react=("todos",)):
        def load(self) -> str:
            return "loaded"

    widget = Widget()
    with (
        request_scope(),
        patch("pyjinhx.reactive.component.cache_put") as spy,
    ):
        widget.load()

    assert spy.call_args.kwargs["react_keys"] == ("todos",)


def test_declared_react_keys_make_the_entry_evictable():
    from pyjinhx.reactive.cache import invalidate

    calls: list[int] = []

    class Widget(ReactiveComponent, react=("todos",)):
        def load(self) -> str:
            calls.append(1)
            return "loaded"

    widget = Widget()
    with request_scope():
        widget.load()
        invalidate(["todos"])
        widget.load()

    assert len(calls) == 2


def test_react_keys_default_to_empty():
    class Widget(ReactiveComponent):
        def load(self) -> str:
            return "loaded"

    assert Widget._pjx_react_keys == ()


def test_enum_react_keys_are_normalized_to_their_values():
    from pyjinhx.reactive.keys import MutationKey

    class Keys(MutationKey):
        TODOS = "todos"

    class Widget(ReactiveComponent, react=(Keys.TODOS,)):
        def load(self) -> str:
            return "loaded"

    assert Widget._pjx_react_keys == ("todos",)


def test_subclass_without_load_returns_none():
    class Widget(ReactiveComponent):
        pass

    assert Widget().load() is None


def test_base_component_registration_still_fires():
    """super().__pydantic_init_subclass__() is not skipped - BaseComponent's
    reserved-field validation still rejects a subclass that shadows auto_id."""
    with pytest.raises(TypeError, match="auto_id"):

        class Widget(ReactiveComponent):
            auto_id: bool = False  # pyright: ignore[reportIncompatibleVariableOverride]


def test_the_descriptor_is_attached_to_reactive_subclasses():
    class Widget(ReactiveComponent):
        def load(self) -> str:
            return "loaded"

    assert Widget.__pjx_descriptor__ is not None


def test_resolve_pjx_key_field_returns_none_when_unmarked():
    from pyjinhx.reactive.component import resolve_pjx_key_field

    class Widget(ReactiveComponent):
        name: str = ""

    assert resolve_pjx_key_field(Widget) is None


def test_resolve_pjx_key_field_finds_an_annotated_field():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey, resolve_pjx_key_field

    class Widget(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

    assert resolve_pjx_key_field(Widget) == "row_id"


def test_resolve_pjx_key_field_finds_a_field_wrapped_marker():
    from typing import Annotated

    from pydantic import Field

    from pyjinhx.reactive.component import PjxKey, resolve_pjx_key_field

    class Widget(ReactiveComponent):
        row_id: Annotated[int, PjxKey(), Field(default=0)]

    assert resolve_pjx_key_field(Widget) == "row_id"


def test_two_pjx_key_fields_raise_at_class_definition():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    with pytest.raises(TypeError, match="PjxKey"):

        class Widget(ReactiveComponent):
            a: Annotated[int, PjxKey()] = 0
            b: Annotated[int, PjxKey()] = 0


def test_unmarked_instances_share_one_cache_entry():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        def load(self) -> str:
            calls.append(1)
            return "loaded"

    with request_scope():
        Widget().load()
        Widget().load()

    assert len(calls) == 1


def test_distinct_pjx_key_values_load_independently():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    calls: list[int] = []

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        def load(self) -> int:
            calls.append(self.row_id)
            return self.row_id * 10

    with request_scope():
        assert Row(row_id=1).load() == 10
        assert Row(row_id=2).load() == 20

    assert calls == [1, 2]


def test_equal_pjx_key_values_share_one_cache_entry():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    calls: list[int] = []

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        def load(self) -> str:
            calls.append(self.row_id)
            return "loaded"

    with request_scope():
        Row(row_id=1).load()
        Row(row_id=1).load()

    assert len(calls) == 1


def test_pjx_key_equal_values_share_object_identity():
    """Equal PjxKey values hit the same cache entry, so the second load() gets
    back the very same object — not an equal copy from a re-run body."""
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        def load(self) -> dict[str, int]:
            return {"row_id": self.row_id}

    with request_scope():
        result_a = Row(row_id=1).load()
        result_b = Row(row_id=1).load()

    assert result_a is result_b


def test_pjx_key_distinct_values_differ_in_identity():
    """Distinct PjxKey values are distinct cache entries, so each load() body
    runs and yields its own object — even when the two results compare equal."""
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        def load(self) -> dict[str, str]:
            return {"shape": "same"}

    with request_scope():
        result_a = Row(row_id=1).load()
        result_b = Row(row_id=2).load()

    assert result_a == result_b
    assert result_a is not result_b
