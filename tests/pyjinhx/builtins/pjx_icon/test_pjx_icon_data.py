"""The vendored Lucide icon map is well-formed."""

from pyjinhx.builtins.ui.pjx_icon._icons import ICON_NAMES, ICONS


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


def test_regression_icons_present():
    """Names that were missing from earlier vendor passes (issues #99, #200, #204)."""
    for name in (
        "building",
        "triangle-alert",
        "brain",
        "pin",
        "pin-off",
        "ellipsis",
        "ellipsis-vertical",
    ):
        assert name in ICONS, f"icon {name!r} missing from ICONS"
        assert ICONS[name], f"icon {name!r} has empty inner markup"
        assert "<svg" not in ICONS[name], f"icon {name!r}: inner markup only"
