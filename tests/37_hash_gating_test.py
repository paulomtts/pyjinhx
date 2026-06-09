from markupsafe import Markup

from pyjinhx.reactive import oob_swaps
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.reactive.reactive_panel import ReactivePanel


def _fresh_counter_hash() -> str:
    instance = ReactiveCounter.load()
    instance.id = "counter"
    return instance.state_hash()


def _fresh_panel_hash() -> str:
    instance = ReactivePanel.load()
    instance.id = "panel"
    return instance.state_hash()


def test_matching_hash_is_skipped():
    store.state["remaining"] = 4
    manifest = [
        {"id": "counter", "type": "ReactiveCounter", "hash": _fresh_counter_hash()}
    ]
    out = oob_swaps({"todos"}, manifest)
    assert isinstance(out, Markup)
    assert str(out) == ""


def test_mismatched_hash_is_swapped():
    store.state["remaining"] = 4
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale-hash"}]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "4 left" in out


def test_missing_hash_is_swapped():
    store.state["remaining"] = 4
    manifest = [{"id": "counter", "type": "ReactiveCounter"}]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='counter']" in out


def test_all_matching_returns_empty_markup():
    store.state["remaining"] = 7
    store.state["completed"] = 2
    clear = ReactiveClearButton.load()
    clear.id = "clear-btn"
    manifest = [
        {"id": "counter", "type": "ReactiveCounter", "hash": _fresh_counter_hash()},
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": clear.state_hash()},
    ]
    assert str(oob_swaps({"todos"}, manifest)) == ""


def test_unchanged_parent_does_not_suppress_changed_child():
    store.state["remaining"] = 9
    manifest = [
        {"id": "panel", "type": "ReactivePanel", "hash": _fresh_panel_hash()},
        {"id": "counter", "type": "ReactiveCounter", "hash": "stale-hash"},
    ]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='panel']" not in out
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "9 left" in out


def test_changed_parent_still_dedups_changed_child():
    store.state["remaining"] = 3
    manifest = [
        {"id": "panel", "type": "ReactivePanel", "hash": "stale-a"},
        {"id": "counter", "type": "ReactiveCounter", "hash": "stale-b"},
    ]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='panel']" in out
    assert "outerHTML:[data-pjx-id='counter']" not in out
    assert "3 left" in out
