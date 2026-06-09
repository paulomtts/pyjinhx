from pyjinhx.reactive import oob_swaps  # noqa: F401
from tests.reactive_test_support import reactive_client, record_mutation
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.unified_component import UnifiedComponent


def test_pending_mutations_drive_oob_swaps():
    store.state["completed"] = 4
    primary = ReactiveCounter(id="counter", remaining=0)
    manifest = [
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
    ]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(primary.render())
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "Clear (4)" in out


def test_no_pending_mutations_skips_oob():
    store.state["completed"] = 4
    primary = ReactiveCounter(id="counter", remaining=0)
    manifest = [
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
    ]
    with reactive_client(manifest):
        out = str(primary.render())
    assert "outerHTML:[data-pjx-id='clear-btn']" not in out


def test_non_reactive_primary_defaults_to_no_swaps():
    store.state["completed"] = 4
    primary = UnifiedComponent(id="u1", text="hi")
    manifest = [
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}
    ]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(primary.render())
    assert "outerHTML:[data-pjx-id='clear-btn']" not in out
    assert "hi" in out
