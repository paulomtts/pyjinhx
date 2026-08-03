"""Cheap CI guard: the v0.36 and v2 bench pages must reference the same components.

Not timing-sensitive — no rendering happens here, only manifest comparison.
"""

from tests.fixtures.bench_builtin_heavy import V0_MANIFEST, V2_MANIFEST, build_v0_page, build_v2_page


def test_manifests_are_the_same_logical_component_set() -> None:
    assert V0_MANIFEST == V2_MANIFEST


def test_manifest_is_not_trivially_small() -> None:
    # Guards against someone gutting the page to make the bench look good.
    assert len(V0_MANIFEST) >= 20


def test_every_manifest_entry_appears_in_both_page_sources() -> None:
    v0_src = build_v0_page(rows=3)
    v2_src = build_v2_page(rows=3)
    for logical in V0_MANIFEST:
        assert logical in v0_src, f"{logical} missing from v0 page source"
        assert logical in v2_src, f"{logical} missing from v2 page source"
