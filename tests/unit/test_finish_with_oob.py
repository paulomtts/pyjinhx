from pathlib import Path

from markupsafe import Markup

from pyjinhx.reactive import _finish_with_oob, _mounted_ids_in
from pyjinhx.renderer import Renderer
from tests.reactive_test_support import reactive_client, record_mutation
from tests.ui.reactive import store
from tests.ui.reactive.reactive_counter import ReactiveCounter  # noqa: F401 (registers)
from tests.ui.reactive.reactive_clear_button import ReactiveClearButton  # noqa: F401
from tests.ui.unified_component import UnifiedComponent  # noqa: F401 (registers)

_UI_DIR = Path(__file__).resolve().parents[1] / "ui"


def test_mounted_ids_extracts_double_quoted_markers():
    html = '<div data-pjx-id="counter"></div><span data-pjx-id="clear-btn"></span>'
    assert _mounted_ids_in(html) == {"counter", "clear-btn"}


def test_mounted_ids_empty_on_plain_html():
    assert _mounted_ids_in("<div>no markers</div>") == set()


def test_mounted_ids_accepts_markup():
    assert _mounted_ids_in(Markup('<div data-pjx-id="x"></div>')) == {"x"}


def test_appends_swaps_for_dirtied_mounted_region():
    store.state["remaining"] = 2
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(_finish_with_oob("<div id='result'>done</div>"))
    assert "<div id='result'>done</div>" in out
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "2 left" in out


def test_passthrough_without_backend():
    record_mutation("todos")
    out = _finish_with_oob("<div>x</div>")
    assert str(out) == "<div>x</div>"


def test_passthrough_without_pending_mutations():
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        out = _finish_with_oob("<div>x</div>")
    assert str(out) == "<div>x</div>"


def test_emits_once_per_scope():
    store.state["remaining"] = 1
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        first = str(_finish_with_oob("<div>a</div>"))
        second = str(_finish_with_oob("<div>b</div>"))
    assert "outerHTML:[data-pjx-id='counter']" in first
    assert second == "<div>b</div>"


def test_excludes_region_already_in_body():
    store.state["remaining"] = 3
    manifest = [
        {"id": "counter", "type": "ReactiveCounter", "hash": "stale"},
        {"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"},
    ]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(_finish_with_oob('<div data-pjx-id="counter">3 left</div>'))
    assert "outerHTML:[data-pjx-id='counter']" not in out
    assert "outerHTML:[data-pjx-id='clear-btn']" in out


def test_base_render_fans_out_for_nonreactive():
    Renderer.set_default_environment(_UI_DIR)
    store.state["remaining"] = 4
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(UnifiedComponent(id="result", text="done").render())
    assert "result" in out
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "4 left" in out


def test_base_render_unchanged_without_backend():
    Renderer.set_default_environment(_UI_DIR)
    record_mutation("todos")
    out = str(UnifiedComponent(id="result", text="done").render())
    assert "outerHTML:" not in out


def test_reactive_response_fans_out_for_raw_string():
    from pyjinhx.reactive import reactive_response

    store.state["remaining"] = 9
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(reactive_response("<p>no component here</p>"))
    assert "<p>no component here</p>" in out
    assert "outerHTML:[data-pjx-id='counter']" in out
    assert "9 left" in out


def test_class_render_does_not_double_invalidate(monkeypatch):
    # The class-render path invalidates before rendering the primary, so the
    # OOB tail must NOT invalidate again (avoids a redundant publish).
    from pyjinhx import cache as cache_mod

    calls = []
    original = cache_mod.LoadCache.invalidate

    def counting_invalidate(keys):
        calls.append(set(keys))
        return original(keys)

    monkeypatch.setattr(cache_mod.LoadCache, "invalidate", counting_invalidate)

    store.state["remaining"] = 2
    manifest = [{"id": "clear-btn", "type": "ReactiveClearButton", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        out = str(ReactiveCounter.render())

    assert "outerHTML:[data-pjx-id='clear-btn']" in out
    # one invalidate from record_mutation, one from the bundle's pre-primary
    # step; the OOB tail must NOT add a third (it skips invalidation).
    assert len(calls) == 2
