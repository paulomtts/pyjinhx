"""Reactive OOB swaps deliver missing INLINE assets, deduped by client token."""
import json

import pytest
from jinja2 import Environment, FileSystemLoader

from pyjinhx import MutationKey, ReactiveComponent
from pyjinhx.assets import asset_token, should_emit_asset
from pyjinhx.client import ClientBackend, LoadedAssets, PJX_ASSETS_HEADER
from pyjinhx.integrations.fastapi import FastAPIClientBackend
from pyjinhx.reactive import oob_swaps
from pyjinhx.renderer import Renderer


# ---------------------------------------------------------------------------
# Unit-level token + dedup tests (Step 2 / 4)
# ---------------------------------------------------------------------------


def test_asset_token_is_stable_for_same_path(tmp_path):
    p = str(tmp_path / "x.css")
    assert asset_token(p) == asset_token(p)


def test_should_emit_when_token_absent():
    assert should_emit_asset("t1", frozenset(), dedup_enabled=True) is True
    assert should_emit_asset("t1", frozenset({"t2"}), dedup_enabled=True) is True


def test_should_not_emit_when_token_present():
    assert should_emit_asset("t1", frozenset({"t1"}), dedup_enabled=True) is False


def test_dedup_disabled_always_emits():
    assert should_emit_asset("t1", frozenset({"t1"}), dedup_enabled=False) is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


def _make_backend(
    manifest: list[dict],
    *,
    loaded_tokens: list[str] | None = None,
) -> FastAPIClientBackend:
    headers: dict[str, str] = {
        "X-PJX-Mounted": json.dumps(manifest),
    }
    if loaded_tokens is not None:
        headers[PJX_ASSETS_HEADER] = json.dumps(loaded_tokens)
    return FastAPIClientBackend(FakeRequest(headers))


class _SwapKeys(MutationKey):
    ITEMS = "swap_items"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def asset_env(tmp_path):
    """Temp dir with a template, CSS, and JS file; wired as the default env."""
    (tmp_path / "swap_widget.html").write_text(
        '<div id="{{ id }}" class="swap-widget">{{ count }}</div>'
    )
    (tmp_path / "swap-widget.css").write_text(".swap-widget { color: teal; }")
    (tmp_path / "swap-widget.js").write_text("console.log('swap-widget');")
    env = Environment(loader=FileSystemLoader(str(tmp_path)))
    Renderer.set_default_environment(env)
    return tmp_path


# ---------------------------------------------------------------------------
# Reactive component factories
# ---------------------------------------------------------------------------


def _make_swap_widget(asset_env):
    """SwapWidget: reacts to ITEMS, carries CSS + JS extra assets."""
    css_path = str(asset_env / "swap-widget.css")
    js_path = str(asset_env / "swap-widget.js")

    class SwapWidget(ReactiveComponent, react={_SwapKeys.ITEMS}, pjx_replace=True):
        _pjx_template = "SwapWidget"
        count: int = 0

        @classmethod
        def load(cls) -> "SwapWidget":
            return cls(id="swap-widget", count=1, css=[css_path], js=[js_path])

    return SwapWidget, css_path, js_path


def _make_swap_widget_css_only(asset_env):
    """SwapWidgetCss: same but CSS only, used for the shared-asset dedup test."""
    css_path = str(asset_env / "swap-widget.css")

    class SwapWidgetCss(ReactiveComponent, react={_SwapKeys.ITEMS}, pjx_replace=True):
        _pjx_template = "SwapWidget"
        count: int = 0

        @classmethod
        def load(cls) -> "SwapWidgetCss":
            return cls(id="swap-widget-css", count=1, css=[css_path])

    return SwapWidgetCss, css_path


# ---------------------------------------------------------------------------
# Integration tests: #96 – OOB swaps deliver missing assets
# ---------------------------------------------------------------------------


def test_oob_swap_delivers_css_when_absent(asset_env):
    """#96 repro: CSS is delivered via OOB head injection when client hasn't loaded it."""
    _cls, css_path, js_path = _make_swap_widget(asset_env)

    manifest = [{"id": "swap-widget", "type": "SwapWidget", "hash": "stale"}]
    backend = _make_backend(manifest)  # no X-PJX-Assets → nothing loaded

    with ClientBackend.scope(backend):
        result = str(oob_swaps({_SwapKeys.ITEMS}, manifest))

    token = asset_token(css_path)
    assert f'data-pjx-asset="{token}"' in result
    assert 'hx-swap-oob="beforeend:head"' in result
    assert ".swap-widget { color: teal; }" in result


def test_oob_swap_delivers_js_when_absent(asset_env):
    """JS is delivered via OOB head injection when client hasn't loaded it."""
    _cls, css_path, js_path = _make_swap_widget(asset_env)

    manifest = [{"id": "swap-widget", "type": "SwapWidget", "hash": "stale"}]
    backend = _make_backend(manifest)

    with ClientBackend.scope(backend):
        result = str(oob_swaps({_SwapKeys.ITEMS}, manifest))

    token = asset_token(js_path)
    assert f'data-pjx-asset="{token}"' in result
    assert "console.log('swap-widget');" in result


def test_oob_swap_skips_already_loaded_css(asset_env):
    """CSS token reported by client in X-PJX-Assets is not re-emitted."""
    _cls, css_path, js_path = _make_swap_widget(asset_env)

    css_token = asset_token(css_path)
    manifest = [{"id": "swap-widget", "type": "SwapWidget", "hash": "stale"}]
    backend = _make_backend(manifest, loaded_tokens=[css_token])

    with ClientBackend.scope(backend):
        result = str(oob_swaps({_SwapKeys.ITEMS}, manifest))

    # CSS must NOT be re-injected
    assert ".swap-widget { color: teal; }" not in result
    # JS is still missing so it must appear
    js_token = asset_token(js_path)
    assert f'data-pjx-asset="{js_token}"' in result


def test_oob_swap_emits_nothing_when_all_loaded(asset_env):
    """No OOB asset injection when the client already has every asset token."""
    _cls, css_path, js_path = _make_swap_widget(asset_env)

    css_token = asset_token(css_path)
    js_token = asset_token(js_path)
    manifest = [{"id": "swap-widget", "type": "SwapWidget", "hash": "stale"}]
    backend = _make_backend(manifest, loaded_tokens=[css_token, js_token])

    with ClientBackend.scope(backend):
        result = str(oob_swaps({_SwapKeys.ITEMS}, manifest))

    assert ".swap-widget { color: teal; }" not in result
    assert "console.log('swap-widget');" not in result


def test_two_regions_sharing_asset_emit_it_once(asset_env):
    """Two swapped regions that share a CSS asset emit that asset exactly once."""
    _cls, css_path = _make_swap_widget_css_only(asset_env)

    manifest = [
        {"id": "swap-widget-css-a", "type": "SwapWidgetCss", "hash": "stale-a"},
        {"id": "swap-widget-css-b", "type": "SwapWidgetCss", "hash": "stale-b"},
    ]
    backend = _make_backend(manifest)

    with ClientBackend.scope(backend):
        result = str(oob_swaps({_SwapKeys.ITEMS}, manifest))

    css_content = ".swap-widget { color: teal; }"
    assert result.count(css_content) == 1


# ---------------------------------------------------------------------------
# LoadedAssets.parse unit tests
# ---------------------------------------------------------------------------


def test_loaded_assets_parse_from_request_header(tmp_path):
    """LoadedAssets.parse reads tokens from a request-like object's header."""
    css_path = str(tmp_path / "x.css")
    token = asset_token(css_path)
    request = FakeRequest({PJX_ASSETS_HEADER: json.dumps([token])})
    backend = FastAPIClientBackend(request)
    loaded = LoadedAssets.parse(backend)
    assert token in loaded


def test_loaded_assets_parse_returns_empty_frozenset_when_absent():
    """LoadedAssets.parse returns frozenset() for None / empty / missing header."""
    assert LoadedAssets.parse(None) == frozenset()
    assert LoadedAssets.parse("") == frozenset()
    assert LoadedAssets.parse(FakeRequest()) == frozenset()
