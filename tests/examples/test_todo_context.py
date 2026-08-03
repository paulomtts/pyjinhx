"""TodoAppContext is a frozen dataclass the app can hand to context_factory."""

import dataclasses

import pytest

from pyjinhx import AppContext

from examples.todo import store
from examples.todo.context import TodoAppContext


def test_is_a_frozen_dataclass_subclass_of_app_context():
    assert issubclass(TodoAppContext, AppContext)
    assert dataclasses.is_dataclass(TodoAppContext)
    assert TodoAppContext.__dataclass_params__.frozen is True


def test_exposes_whatever_store_it_was_given():
    sentinel = object()
    assert TodoAppContext(store=sentinel).store is sentinel


def test_rejects_mutation_after_construction():
    ctx = TodoAppContext(store=store)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.store = None  # type: ignore[misc]


def test_works_as_a_context_factory_return_value():
    factory = lambda request: TodoAppContext(store=store)  # noqa: E731
    ctx = factory(object())
    assert ctx.store.total() == store.total()
