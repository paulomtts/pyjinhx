from pyjinhx import oob_swaps  # noqa: F401  (ensures package import side effects)
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.unified_component import UnifiedComponent


def test_dirtied_defaults_to_primary_depends_on():
    store.state["completed"] = 4
    primary = ReactiveCounter(id="counter", remaining=0)  # depends_on = {"todos"}
    # dirtied omitted -> defaults to the primary's depends_on ({"todos"}),
    # so the todos-dependent clear button is swapped.
    out = str(
        primary.render(
            mounted=[
                {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
            ]
        )
    )
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (4)" in out


def test_explicit_empty_dirtied_is_respected():
    store.state["completed"] = 4
    primary = ReactiveCounter(id="counter", remaining=0)
    out = str(
        primary.render(
            dirtied=set(),
            mounted=[
                {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
            ],
        )
    )
    # explicit empty set -> nothing dirtied -> no swaps
    assert "outerHTML:[data-pjx-id='clear-btn']" not in out


def test_non_reactive_primary_defaults_to_no_swaps():
    store.state["completed"] = 4
    primary = UnifiedComponent(id="u1", text="hi")  # not reactive, no depends_on
    out = str(
        primary.render(
            mounted=[
                {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
            ]
        )
    )
    assert "outerHTML:[data-pjx-id='clear-btn']" not in out
    assert "hi" in out
