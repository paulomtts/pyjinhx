"""pjxManifest(): the DOM -> mounted-regions scan behind X-PJX-Mounted."""

from __future__ import annotations


def test_manifest_is_empty_without_mounted_regions(pjx_page):
    page = pjx_page("<div>plain</div>")
    assert page.evaluate("pjx.manifest()") == []


def test_manifest_reads_id_type_and_hash(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1"></div>'
    )
    assert page.evaluate("pjx.manifest()") == [
        {"id": "a1", "type": "Card", "hash": "h1"}
    ]


def test_manifest_lists_every_mounted_region_in_document_order(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1">'
        '<span data-pjx-id="b2" data-pjx-type="Badge" data-pjx-hash="h2"></span>'
        "</div>"
    )
    assert [entry["id"] for entry in page.evaluate("pjx.manifest()")] == ["a1", "b2"]


def test_manifest_includes_load_only_when_non_empty(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Row" data-pjx-hash="h1" data-pjx-load="7"></div>'
        '<div data-pjx-id="a2" data-pjx-type="Row" data-pjx-hash="h2" data-pjx-load=""></div>'
    )
    entries = page.evaluate("pjx.manifest()")
    assert entries[0]["load"] == "7"
    assert "load" not in entries[1]


def test_manifest_skips_elements_without_an_id(pjx_page):
    page = pjx_page('<div data-pjx-type="Card" data-pjx-hash="h1"></div>')
    assert page.evaluate("pjx.manifest()") == []


def test_manifest_tolerates_missing_type_and_hash(pjx_page):
    page = pjx_page('<div data-pjx-id="a1"></div>')
    assert page.evaluate("pjx.manifest()") == [{"id": "a1", "type": None, "hash": None}]


def test_manifest_omits_undefined_type_and_hash_over_the_wire(pjx_page):
    page = pjx_page('<div data-pjx-id="a1"></div>')
    assert page.evaluate("JSON.stringify(pjx.manifest())") == '[{"id":"a1"}]'


def test_manifest_reflects_the_dom_at_call_time(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1"></div>'
    )
    page.evaluate("document.querySelector('[data-pjx-id]').remove()")
    assert page.evaluate("pjx.manifest()") == []
