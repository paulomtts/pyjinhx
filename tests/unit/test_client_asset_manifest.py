from pyjinhx.reactive import oob_swaps
from pyjinhx.utils import read_client_runtime
from tests.ui.reactive.reactive_counter import ReactiveCounter


def test_runtime_source_reports_assets_header():
    source = read_client_runtime()
    assert "X-PJX-Assets" in source
    assert 'link[rel="stylesheet"][href]' in source


def test_oob_swaps_emit_no_assets():
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    rendered = str(oob_swaps({"todos"}, manifest))

    assert "<link" not in rendered
    assert "<script" not in rendered
