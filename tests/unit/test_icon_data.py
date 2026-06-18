"""The vendored Lucide icon map is well-formed."""
from pyjinhx.builtins.ui.pjx_icon._icons import ICONS, ICON_NAMES


def test_seed_icons_present():
    for name in ("chevron-right", "plus", "x", "search", "user"):
        assert name in ICONS, name


def test_values_are_inner_markup_only():
    for name, inner in ICONS.items():
        assert inner, name
        assert "<svg" not in inner, f"{name}: must be inner markup, not a full <svg>"
        assert "</svg>" not in inner, name


def test_icon_names_matches_keys():
    assert ICON_NAMES == tuple(ICONS)


def test_issue_99_icons_present():
    """building, triangle-alert and brain were missing from the vendored set (issue #99)."""
    for name in ("building", "triangle-alert", "brain"):
        assert name in ICONS, f"icon {name!r} missing from ICONS"
        inner = ICONS[name]
        assert inner, f"icon {name!r} has empty inner markup"
        assert "<svg" not in inner, f"icon {name!r}: must be inner markup only, not a full <svg>"
