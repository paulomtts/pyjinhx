"""
Class-form render(): the auto-loading route entry point.

`Cls.render(key, dirtied=, mounted=)` loads the primary itself (no developer
`load()` call), renders it, and appends OOB swaps for dependents — while
`instance.render(...)` keeps the original instance-render contract.
"""

import pytest
from markupsafe import Markup

from pyjinhx import oob_swaps  # noqa: F401 (package import side effects)
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.reactive.user_row import UserRow


def _row(i):
    return {"id": f"user-row-{i}", "type": "UserRow", "key": str(i), "hash": "stale"}


# --- singleton class form -----------------------------------------------------


def test_singleton_class_form_loads_primary_and_swaps_dependents():
    store.state["remaining"] = 2
    store.state["completed"] = 5
    out = str(
        ReactiveCounter.render(
            dirtied={"todos"},
            mounted=[
                {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
            ],
        )
    )
    assert "2 left" in out
    assert 'data-pjx-id="counter"' in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (5)" in out


def test_singleton_class_form_excludes_primary_from_oob():
    store.state["remaining"] = 1
    out = str(
        ReactiveCounter.render(
            dirtied={"todos"},
            mounted=[{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}],
        )
    )
    assert "1 left" in out
    assert "outerHTML:[data-pjx-id='counter']" not in out


# --- keyed class form ---------------------------------------------------------


def test_keyed_class_form_renders_keyed_primary():
    out = str(UserRow.render("1", dirtied={"user:1"}, mounted=[]))
    assert "Alice" in out
    assert 'data-pjx-id="user-row-1"' in out
    assert 'data-pjx-key="1"' in out
    assert 'data-pjx-type="UserRow"' in out


def test_keyed_class_form_swaps_only_dirtied_siblings():
    out = str(
        UserRow.render(
            "1",
            dirtied={"user:1"},
            mounted=[_row(1), _row(2), _row(3)],
        )
    )
    assert 'data-pjx-id="user-row-1"' in out
    assert "outerHTML:[data-pjx-id='user-row-1']" not in out
    assert "outerHTML:[data-pjx-id='user-row-2']" not in out
    assert "outerHTML:[data-pjx-id='user-row-3']" not in out


def test_keyed_collection_tier_swaps_siblings_out_of_band():
    out = str(
        UserRow.render(
            "1",
            dirtied={"users"},
            mounted=[_row(1), _row(2), _row(3)],
        )
    )
    assert "outerHTML:[data-pjx-id='user-row-1']" not in out
    assert "outerHTML:[data-pjx-id='user-row-2']" in out and "Bob" in out
    assert "outerHTML:[data-pjx-id='user-row-3']" in out and "Carol" in out


def test_keyed_dirtied_defaults_to_interpolated_reacts_to():
    out = str(UserRow.render("1", mounted=[_row(1), _row(2)]))
    assert "outerHTML:[data-pjx-id='user-row-2']" in out


# --- guards -------------------------------------------------------------------


def test_keyed_without_key_raises():
    with pytest.raises(TypeError, match="instance-keyed"):
        UserRow.render(dirtied={"users"}, mounted=[])


def test_singleton_with_key_raises():
    with pytest.raises(TypeError, match="type-singleton"):
        ReactiveCounter.render("99", mounted=[])


# --- contract preservation ----------------------------------------------------


def test_class_form_equals_load_then_render():
    store.state["remaining"] = 3
    store.state["completed"] = 2
    manifest = [{"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}]
    via_class = str(ReactiveCounter.render(dirtied={"todos"}, mounted=manifest))
    via_load = str(ReactiveCounter.load().render(dirtied={"todos"}, mounted=manifest))
    assert via_class == via_load


def test_class_form_returns_markup_and_does_not_escape():
    store.state["remaining"] = 2
    result = ReactiveCounter.render(dirtied={"todos"}, mounted=[])
    assert isinstance(result, Markup)
    assert "&lt;" not in str(result)


def test_instance_form_still_renders_self():
    counter = ReactiveCounter(id="counter", remaining=99)
    assert "99 left" in str(counter.render())
