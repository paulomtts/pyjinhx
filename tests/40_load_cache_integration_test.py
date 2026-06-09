from pyjinhx.reactive import oob_swaps
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401


def test_oob_swaps_invalidates_dirtied_before_loading():
    store.state["remaining"] = 1
    warm = ReactiveCounter.load()
    assert warm.remaining == 1
    store.state["remaining"] = 5
    out = str(
        oob_swaps(
            {"todos"},
            [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}],
        )
    )
    assert "5 left" in out
    assert "1 left" not in out


def test_reactive_render_invalidates_dirtied():
    from tests.reactive_test_support import reactive_client, record_mutation

    store.state["completed"] = 2
    warm = ReactiveClearButton.load()
    assert warm.completed == 2
    store.state["completed"] = 9
    primary = ReactiveCounter(id="counter", remaining=0)
    manifest = [{"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(primary.render())
    assert "Clear (9)" in out
    assert "Clear (2)" not in out
