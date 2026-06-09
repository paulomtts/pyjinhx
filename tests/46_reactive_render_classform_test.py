"""
Class-form render(): the auto-loading route entry point.

``Cls.render(*args)`` loads the primary itself (no developer ``load()`` call),
renders it, and appends OOB swaps for dependents when a ``ClientBackend`` is
active and mutations are pending.
"""

import pytest
from markupsafe import Markup

from pyjinhx import oob_swaps  # noqa: F401
from tests.reactive_test_support import reactive_client, record_mutation
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.reactive.user_row import UserRow


def _row(i):
    return {"id": f"user-row-{i}", "type": "UserRow", "load": str(i), "hash": "stale"}


def test_singleton_class_form_loads_primary_and_swaps_dependents():
    store.state["remaining"] = 2
    store.state["completed"] = 5
    manifest = [{"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(ReactiveCounter.render())
    assert "2 left" in out
    assert 'data-pjx-id="counter"' in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (5)" in out


def test_singleton_class_form_excludes_primary_from_oob():
    store.state["remaining"] = 1
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(ReactiveCounter.render())
    assert "1 left" in out
    assert "outerHTML:[data-pjx-id='counter']" not in out


def test_keyed_class_form_renders_keyed_primary():
    with reactive_client([]):
        record_mutation("users")
        out = str(UserRow.render("1"))
    assert "Alice" in out
    assert 'data-pjx-id="user-row-1"' in out
    assert 'data-pjx-load="1"' in out
    assert 'data-pjx-type="UserRow"' in out


def test_keyed_class_form_swaps_siblings_on_collection_dirty():
    manifest = [_row(1), _row(2), _row(3)]
    with reactive_client(manifest, trigger_id="user-row-1"):
        record_mutation("users")
        out = str(UserRow.render("1"))
    assert 'data-pjx-id="user-row-1"' in out
    assert "outerHTML:[data-pjx-id='user-row-1']" not in out
    assert "outerHTML:[data-pjx-id='user-row-2']" in out and "Bob" in out
    assert "outerHTML:[data-pjx-id='user-row-3']" in out and "Carol" in out


def test_keyed_without_load_arg_raises():
    with pytest.raises(TypeError, match="instance-keyed"):
        UserRow.render()


def test_singleton_with_key_raises():
    with pytest.raises(TypeError, match="type-singleton"):
        ReactiveCounter.render("99")


def test_class_form_returns_markup_and_does_not_escape():
    store.state["remaining"] = 2
    with reactive_client([]):
        record_mutation("todos")
        result = ReactiveCounter.render()
    assert isinstance(result, Markup)
    assert "&lt;" not in str(result)


def test_instance_form_still_renders_self():
    counter = ReactiveCounter(id="counter", remaining=99)
    assert "99 left" in str(counter.render())


def test_dependent_trigger_still_swaps_oob():
    # Regression: the clicked element (X-PJX-Trigger) is a dependent distinct from
    # the primary, so it must still OOB-update -- it was wrongly excluded before.
    store.state["remaining"] = 2
    store.state["completed"] = 5
    manifest = [{"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}]
    with reactive_client(manifest, trigger_id="clear-btn"):
        record_mutation("todos")
        out = str(ReactiveCounter.render())
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (5)" in out
