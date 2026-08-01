"""pjxLoadedAssets(): the asset tokens already on the page, behind X-PJX-Assets."""

from __future__ import annotations


def test_loaded_assets_is_empty_without_asset_nodes(pjx_page):
    page = pjx_page("<div></div>")
    assert page.evaluate("pjx.loadedAssets()") == []


def test_loaded_assets_collects_tokens_from_head_and_body(pjx_page):
    page = pjx_page(
        '<script data-pjx-asset="card.js"></script>',
        head='<style data-pjx-asset="card.css"></style>',
    )
    assert sorted(page.evaluate("pjx.loadedAssets()")) == ["card.css", "card.js"]


def test_loaded_assets_dedupes_repeated_tokens(pjx_page):
    page = pjx_page(
        '<style data-pjx-asset="card.css"></style>'
        '<style data-pjx-asset="card.css"></style>'
        '<style data-pjx-asset="badge.css"></style>'
    )
    assert sorted(page.evaluate("pjx.loadedAssets()")) == ["badge.css", "card.css"]
