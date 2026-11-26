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


def _by_id(entries):
    return {entry["id"]: entry for entry in entries}


def test_manifest_records_the_nearest_mounted_ancestor(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1">'
        '<span data-pjx-id="b2" data-pjx-type="Badge" data-pjx-hash="h2"></span>'
        "</div>"
    )
    entries = page.evaluate("pjx.manifest()")
    assert entries[1]["id"] == "b2"
    assert entries[1]["parent"] == "a1"


def test_manifest_omits_parent_for_a_root_region(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1"></div>'
    )
    assert (
        page.evaluate("JSON.stringify(pjx.manifest())")
        == '[{"id":"a1","type":"Card","hash":"h1"}]'
    )
    entries = page.evaluate("pjx.manifest()")
    assert "parent" not in entries[0]


def test_manifest_parent_skips_non_region_ancestors(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1">'
        "<div><section><p>"
        '<span data-pjx-id="b2" data-pjx-type="Badge" data-pjx-hash="h2"></span>'
        "</p></section></div>"
        "</div>"
    )
    entries = _by_id(page.evaluate("pjx.manifest()"))
    assert entries["b2"]["parent"] == "a1"


def test_manifest_parent_is_the_nearest_not_the_outermost(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Shell" data-pjx-hash="h1">'
        '<div data-pjx-id="b2" data-pjx-type="Card" data-pjx-hash="h2">'
        '<span data-pjx-id="c3" data-pjx-type="Badge" data-pjx-hash="h3"></span>'
        "</div>"
        "</div>"
    )
    entries = _by_id(page.evaluate("pjx.manifest()"))
    assert entries["c3"]["parent"] == "b2"
    assert entries["b2"]["parent"] == "a1"
    assert "parent" not in entries["a1"]


def test_manifest_parent_never_names_itself(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1">'
        '<span data-pjx-id="b2" data-pjx-type="Badge" data-pjx-hash="h2"></span>'
        "</div>"
    )
    entries = page.evaluate("pjx.manifest()")
    for entry in entries:
        assert entry.get("parent") != entry["id"]
    by_id = _by_id(entries)
    assert "parent" not in by_id["a1"]
    assert by_id["b2"]["parent"] == "a1"


def test_manifest_sibling_regions_have_no_parent(pjx_page):
    page = pjx_page(
        "<div>"
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1"></div>'
        '<div data-pjx-id="a2" data-pjx-type="Card" data-pjx-hash="h2"></div>'
        "</div>"
    )
    entries = page.evaluate("pjx.manifest()")
    assert [entry["id"] for entry in entries] == ["a1", "a2"]
    assert "parent" not in entries[0]
    assert "parent" not in entries[1]


def test_manifest_parent_ignores_an_ancestor_with_an_empty_id(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Shell" data-pjx-hash="h0">'
        '<div data-pjx-id="">'
        '<span data-pjx-id="b2" data-pjx-type="Badge" data-pjx-hash="h2"></span>'
        "</div>"
        "</div>"
    )
    entries = page.evaluate("pjx.manifest()")
    assert [entry["id"] for entry in entries] == ["a1", "", "b2"]
    # The nearest match has no usable id: no parent, and no climbing past it to a1.
    assert "parent" not in _by_id(entries)["b2"]
    wire = page.evaluate(
        "JSON.stringify(pjx.manifest().filter(function (e) { return e.id === 'b2'; }))"
    )
    assert '"parent"' not in wire


def test_manifest_parent_reflects_the_dom_at_call_time(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1">'
        '<span data-pjx-id="b2" data-pjx-type="Badge" data-pjx-hash="h2"></span>'
        "</div>"
    )
    assert _by_id(page.evaluate("pjx.manifest()"))["b2"]["parent"] == "a1"
    page.evaluate(
        "document.body.appendChild(document.querySelector('[data-pjx-id=\"b2\"]'))"
    )
    assert "parent" not in _by_id(page.evaluate("pjx.manifest()"))["b2"]


def test_manifest_parent_tolerates_a_region_with_no_parent_element(pjx_page):
    page = pjx_page(
        '<div data-pjx-id="b2" data-pjx-type="Badge" data-pjx-hash="h2"></div>'
    )
    # <html> is the one element whose parentElement is null.
    page.evaluate("document.documentElement.setAttribute('data-pjx-id', 'root')")
    entries = _by_id(page.evaluate("pjx.manifest()"))
    assert "parent" not in entries["root"]
    assert entries["b2"]["parent"] == "root"
