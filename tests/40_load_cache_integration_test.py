from pyjinhx import oob_swaps
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401


def test_oob_swaps_invalidates_dirtied_before_loading():
    store.state["remaining"] = 1
    warm = ReactiveCounter.load()  # warm the cache with the old value
    assert warm.remaining == 1
    store.state["remaining"] = 5  # mutate the world
    # oob_swaps must evict {"todos"} and serve the fresh value, not the cached 1.
    out = str(
        oob_swaps(
            {"todos"},
            [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}],
        )
    )
    assert "5 left" in out
    assert "1 left" not in out


def test_reactive_render_invalidates_dirtied():
    store.state["completed"] = 2
    warm = ReactiveClearButton.load()  # warm the cache
    assert warm.completed == 2
    store.state["completed"] = 9
    primary = ReactiveCounter(id="counter", remaining=0)
    out = str(
        primary.render(
            dirtied={"todos"},
            mounted=[
                {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
            ],
        )
    )
    assert "Clear (9)" in out
    assert "Clear (2)" not in out
