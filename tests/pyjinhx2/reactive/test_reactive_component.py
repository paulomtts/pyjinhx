"""ReactiveComponent: the load() wrap installed at class-definition time."""

from typing import Any

import pytest

from pyjinhx2.component import BaseComponent
from pyjinhx2.reactive.component import ReactiveComponent
from pyjinhx2.session import request_scope


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
            return None

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
        patch("pyjinhx2.reactive.component.cache_put") as spy,
    ):
        widget.load()

    assert spy.call_args.kwargs["react_keys"] == ("todos",)


def test_declared_react_keys_make_the_entry_evictable():
    from pyjinhx2.reactive.cache import invalidate

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
    from pyjinhx2.reactive.keys import MutationKey

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
            auto_id: bool = False


def test_the_descriptor_is_attached_to_reactive_subclasses():
    class Widget(ReactiveComponent):
        def load(self) -> str:
            return "loaded"

    assert Widget.__pjx_descriptor__ is not None
