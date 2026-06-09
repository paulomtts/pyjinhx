import json
import os

import pytest

from pyjinhx import (
    AssetMode,
    BaseComponent,
    LoadedAssets,
    PJX_ASSETS_HEADER,
    Renderer,
)
from pyjinhx.reactive.oob import oob_swaps
from pyjinhx.utils import read_client_runtime
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.unified_component import UnifiedComponent


class _Headers:
    def __init__(self, values: dict[str, str]):
        self._values = values

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._values.get(key, default)


class _Client:
    def __init__(self, headers: dict[str, str]):
        self.headers = _Headers(headers)


@pytest.fixture(autouse=True)
def reset_renderer_defaults():
    original_js = Renderer._default_js_mode
    original_css = Renderer._default_css_mode
    original_dedup = Renderer._default_asset_dedup
    original_resolver = Renderer._asset_url_resolver
    original_runtime_url = Renderer._default_runtime_url
    Renderer._default_renderers.clear()
    yield
    Renderer.set_default_js_mode(original_js)
    Renderer.set_default_css_mode(original_css)
    Renderer.set_default_asset_dedup(original_dedup)
    Renderer.set_asset_url_resolver(original_resolver)
    Renderer.set_default_runtime_url(original_runtime_url)
    Renderer._default_renderers.clear()


def test_runtime_source_reports_assets_header():
    source = read_client_runtime()
    assert "X-PJX-Assets" in source
    assert 'link[rel="stylesheet"][href]' in source


def test_loaded_assets_parse_from_request():
    client = _Client(
        {
            PJX_ASSETS_HEADER: json.dumps(
                ["/static/components/greeting.js", "/static/components/greeting.css"]
            )
        }
    )
    loaded = LoadedAssets.parse(client)
    assert loaded == frozenset(
        {"/static/components/greeting.js", "/static/components/greeting.css"}
    )


def test_loaded_assets_parse_invalid_json_returns_empty():
    loaded = LoadedAssets.parse('["not-json"')
    assert loaded == frozenset()


def test_root_reference_render_skips_loaded_assets_when_dedup_enabled():
    Renderer.set_default_js_mode(AssetMode.REFERENCE)
    Renderer.set_default_css_mode(AssetMode.REFERENCE)
    Renderer.set_default_asset_dedup(True)

    def resolver(path: str) -> str:
        return f"/static/{os.path.basename(path)}"

    Renderer.set_asset_url_resolver(resolver)
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )

    loaded = frozenset(
        {
            "/static/unified-component.css",
            "/static/unified-component.js",
        }
    )
    rendered = str(
        UnifiedComponent(id="dedup-1", text="Dedup")._render(
            _renderer=renderer,
            client=list(loaded),
        )
    )

    assert "<link" not in rendered
    assert "<script" not in rendered


def test_root_reference_render_emits_all_when_nothing_loaded():
    Renderer.set_default_js_mode(AssetMode.REFERENCE)
    Renderer.set_default_css_mode(AssetMode.REFERENCE)
    Renderer.set_default_asset_dedup(True)
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )

    rendered = str(UnifiedComponent(id="all-1", text="All")._render(_renderer=renderer))

    assert 'rel="stylesheet"' in rendered
    assert "<script src=" in rendered


def test_root_reference_render_emits_only_missing_assets():
    Renderer.set_default_js_mode(AssetMode.REFERENCE)
    Renderer.set_default_css_mode(AssetMode.REFERENCE)
    Renderer.set_default_asset_dedup(True)

    def resolver(path: str) -> str:
        return f"/static/{os.path.basename(path)}"

    Renderer.set_asset_url_resolver(resolver)
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )

    rendered = str(
        UnifiedComponent(id="delta-1", text="Delta")._render(
            _renderer=renderer,
            client=["/static/unified-component.css"],
        )
    )

    assert "<link" not in rendered
    assert '<script src="/static/unified-component.js"></script>' in rendered


def test_asset_dedup_disabled_ignores_client_header():
    Renderer.set_default_js_mode(AssetMode.REFERENCE)
    Renderer.set_default_css_mode(AssetMode.REFERENCE)
    Renderer.set_default_asset_dedup(False)

    def resolver(path: str) -> str:
        return f"/static/{os.path.basename(path)}"

    Renderer.set_asset_url_resolver(resolver)
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )

    rendered = str(
        UnifiedComponent(id="off-1", text="Off")._render(
            _renderer=renderer,
            client=["/static/unified-component.css", "/static/unified-component.js"],
        )
    )

    assert 'href="/static/unified-component.css"' in rendered
    assert 'src="/static/unified-component.js"' in rendered


def test_reactive_partial_still_emits_no_assets_with_client_header():
    Renderer.set_default_js_mode(AssetMode.REFERENCE)
    Renderer.set_default_css_mode(AssetMode.REFERENCE)
    Renderer.set_default_asset_dedup(True)

    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    client = _Client(
        {
            PJX_ASSETS_HEADER: json.dumps(["/static/components/counter.js"]),
        }
    )
    from tests.reactive_test_support import reactive_client, record_mutation

    with reactive_client(
        manifest,
        extra_headers={
            PJX_ASSETS_HEADER: json.dumps(["/static/components/counter.js"]),
        },
    ):
        record_mutation("todos")
        rendered = str(ReactiveCounter.load().render())

    assert "<link" not in rendered
    assert "<script" not in rendered


def test_oob_swaps_emit_no_assets():
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    rendered = str(oob_swaps({"todos"}, manifest))

    assert "<link" not in rendered
    assert "<script" not in rendered


class Page(BaseComponent):
    pass


def test_runtime_url_skipped_when_already_loaded():
    Renderer.set_default_js_mode(AssetMode.REFERENCE)
    Renderer.set_default_asset_dedup(True)
    Renderer.set_default_runtime_url("/static/pyjinhx/pjx.js")
    renderer = Renderer.get_default_renderer(js_mode=AssetMode.REFERENCE)

    rendered = str(
        Page(id="page")._render(
            source="<html><body>hi</body></html>",
            _renderer=renderer,
            client=["/static/pyjinhx/pjx.js"],
        )
    )

    assert "/static/pyjinhx/pjx.js" not in rendered


@pytest.mark.pjx_runtime
def test_runtime_url_emitted_when_not_loaded():
    Renderer.set_default_js_mode(AssetMode.REFERENCE)
    Renderer.set_default_asset_dedup(True)
    Renderer.set_default_runtime_url("/static/pyjinhx/pjx.js")
    renderer = Renderer.get_default_renderer(js_mode=AssetMode.REFERENCE)

    rendered = str(
        Page(id="page")._render(
            source="<html><body>hi</body></html>",
            _renderer=renderer,
        )
    )

    assert '<script src="/static/pyjinhx/pjx.js"></script>' in rendered
