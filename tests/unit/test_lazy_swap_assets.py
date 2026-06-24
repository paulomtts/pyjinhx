"""#182 — a root render on a *swap* must deliver its not-yet-loaded INLINE assets
through the OOB ``<head>`` channel, not as inline tags in the swapped body.

A ``PJXLazyLoad`` fragment that introduces a builtin whose CSS was never collected
at page render used to emit that CSS inline, where it was stripped on the htmx swap
and the content rendered unstyled. On a swap (signalled by the ``X-PJX-Mounted``
header pjx.js attaches to every request) the render now emits missing assets as
``<style|script data-pjx-asset hx-swap-oob="beforeend:head">`` so pjx.js promotes
them to ``<head>`` and dedups against the live document. Cold full-page renders are
unchanged: assets stay inline.
"""

import os

from pyjinhx.assets import asset_token
from pyjinhx.client import (
    PJX_ASSETS_HEADER,
    PJX_MOUNTED_HEADER,
    ClientBackend,
)
from pyjinhx.finder import Finder
from pyjinhx.integrations.fastapi import FastAPIClientBackend
from tests.ui.unified_component import UnifiedComponent

_UI_DIR = Finder.get_class_directory(UnifiedComponent)
_CSS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.css"))
_JS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.js"))

_CSS_CONTENT = ".test-component { color: red; }"
_JS_CONTENT = "console.log('Button loaded');"


class _FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def _swap_backend(loaded: list[str] | None = None) -> FastAPIClientBackend:
    """A backend mimicking an htmx swap request from pjx.js (X-PJX-Mounted present)."""
    headers = {PJX_MOUNTED_HEADER: "[]"}
    if loaded is not None:
        headers[PJX_ASSETS_HEADER] = "[" + ",".join(f'"{t}"' for t in loaded) + "]"
    return FastAPIClientBackend(_FakeRequest(headers))


def _render() -> str:
    return str(UnifiedComponent(id="lazy-1", text="Lazy").render())


# ---------------------------------------------------------------------------
# Cold full-page render: assets stay inline (unchanged behaviour)
# ---------------------------------------------------------------------------


def test_cold_render_emits_inline_assets():
    rendered = _render()
    assert f'<style data-pjx-asset="{_CSS_TOKEN}">' in rendered
    assert f'<script data-pjx-asset="{_JS_TOKEN}">' in rendered
    assert "hx-swap-oob" not in rendered


# ---------------------------------------------------------------------------
# Swap render: missing assets ride the OOB <head> channel instead
# ---------------------------------------------------------------------------


def test_swap_render_emits_missing_assets_as_head_oob():
    with ClientBackend.scope(_swap_backend()):
        rendered = _render()

    # CSS + JS arrive as head-targeted OOB swaps, carrying their content...
    assert (
        f'<style data-pjx-asset="{_CSS_TOKEN}" hx-swap-oob="beforeend:head">' in rendered
    )
    assert (
        f'<script data-pjx-asset="{_JS_TOKEN}" hx-swap-oob="beforeend:head">' in rendered
    )
    assert _CSS_CONTENT in rendered
    assert _JS_CONTENT in rendered
    # ...and NOT as plain inline tags that the swap would strip.
    assert f'<style data-pjx-asset="{_CSS_TOKEN}">' not in rendered
    assert f'<script data-pjx-asset="{_JS_TOKEN}">' not in rendered


def test_swap_render_dedups_already_loaded_assets():
    with ClientBackend.scope(_swap_backend(loaded=[_CSS_TOKEN, _JS_TOKEN])):
        rendered = _render()

    # Both tokens reported loaded by the client → nothing re-delivered.
    assert _CSS_TOKEN not in rendered
    assert _JS_TOKEN not in rendered
    assert "hx-swap-oob" not in rendered


def test_swap_render_delivers_only_the_missing_asset():
    with ClientBackend.scope(_swap_backend(loaded=[_CSS_TOKEN])):
        rendered = _render()

    # CSS already on the page → skipped; JS still missing → delivered via head OOB.
    assert f'data-pjx-asset="{_CSS_TOKEN}"' not in rendered
    assert (
        f'<script data-pjx-asset="{_JS_TOKEN}" hx-swap-oob="beforeend:head">' in rendered
    )
