from pyjinhx.reactive import oob_swaps
from pyjinhx.utils import read_client_runtime
from tests.ui.reactive.reactive_counter import ReactiveCounter


def test_runtime_source_reports_assets_header():
    source = read_client_runtime()
    assert "X-PJX-Assets" in source
    # Token-based dedup: runtime reports data-pjx-asset tokens, not stylesheet URLs
    assert "data-pjx-asset" in source


def test_oob_swaps_emit_missing_assets():
    """ReactiveCounter carries no CSS/JS so no OOB asset head-injection is added."""
    manifest = [{"id": "counter", "type": ReactiveCounter.__name__, "hash": "stale"}]
    rendered = str(oob_swaps({"todos"}, manifest))

    assert "<link" not in rendered
    # no asset OOB injection (component has no CSS/JS)
    assert 'hx-swap-oob="beforeend:head"' not in rendered
