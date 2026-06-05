from markupsafe import Markup

from pyjinhx import oob_swaps
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401 (registers class)
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.reactive.reactive_panel import ReactivePanel  # noqa: F401
from tests.ui.unified_component import UnifiedComponent  # noqa: F401


def _counter_entry():
    return {"id": "counter", "type": "ReactiveCounter", "hash": "stale"}


def _clear_entry():
    return {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}


def test_swaps_all_dependents_of_dirtied_key():
    store.state["remaining"] = 2
    store.state["completed"] = 1
    out = str(oob_swaps({"todos"}, [_counter_entry(), _clear_entry()]))
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    assert "2 left" in out
    assert "Clear (1)" in out


def test_returns_empty_markup_when_no_dependency_matches():
    out = oob_swaps({"users"}, [_counter_entry()])
    assert isinstance(out, Markup)
    assert str(out) == ""


def test_empty_or_none_manifest_returns_empty():
    assert str(oob_swaps({"todos"}, None)) == ""
    assert str(oob_swaps({"todos"}, "")) == ""
    assert str(oob_swaps({"todos"}, [])) == ""


def test_unknown_type_is_ignored():
    out = oob_swaps({"todos"}, [{"id": "ghost", "type": "DoesNotExist", "hash": "x"}])
    assert str(out) == ""


def test_non_reactive_type_is_ignored():
    out = oob_swaps({"todos"}, [{"id": "u1", "type": "UnifiedComponent", "hash": "x"}])
    assert str(out) == ""


def test_accepts_raw_json_string_manifest():
    store.state["remaining"] = 5
    out = str(
        oob_swaps({"todos"}, '[{"id":"counter","type":"ReactiveCounter","hash":"x"}]')
    )
    assert "5 left" in out
    assert "outerHTML:[data-pjx-id='counter']" in out


def test_invalid_json_string_is_ignored():
    assert str(oob_swaps({"todos"}, "not json")) == ""


def test_nested_child_is_deduplicated():
    store.state["remaining"] = 3
    manifest = [
        {"id": "panel", "type": "ReactivePanel", "hash": "x"},
        {"id": "counter", "type": "ReactiveCounter", "hash": "x"},
    ]
    out = str(oob_swaps({"todos"}, manifest))
    # The panel is swapped (its fresh HTML already contains the counter)...
    assert "outerHTML:[data-pjx-id='panel']" in out
    # ...and the counter is NOT swapped on its own.
    assert "outerHTML:[data-pjx-id='counter']" not in out
    # The counter's content rides inside the panel swap.
    assert "3 left" in out
