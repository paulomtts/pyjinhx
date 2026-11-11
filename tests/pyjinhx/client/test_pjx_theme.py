"""The default theme sheet ships in pyjinhx.client with a path and a reader."""

from __future__ import annotations

import re
from importlib.resources import files

from pyjinhx.client import PJX_THEME_PATH, read_pjx_theme_css

ROOT = re.compile(r"^:root \{(.*?)^\}", re.MULTILINE | re.DOTALL)
MEDIA_DARK = re.compile(
    r"^@media \(prefers-color-scheme: dark\) \{\s*"
    r':root:not\(\[data-pjx-theme="light"\]\) \{(.*?)^  \}\s*^\}',
    re.MULTILINE | re.DOTALL,
)
FORCED_DARK = re.compile(
    r'^\[data-pjx-theme="dark"\] \{(.*?)^\}', re.MULTILINE | re.DOTALL
)
FORCED_LIGHT = re.compile(
    r'^\[data-pjx-theme="light"\] \{(.*?)^\}', re.MULTILINE | re.DOTALL
)
TOKEN_BLOCKS = (ROOT, MEDIA_DARK, FORCED_DARK, FORCED_LIGHT)
DECLARATION = re.compile(r"([\w-]+):\s*([^;]+);")

D1_FAMILIES = (
    "color",
    "font-family",
    "font-size",
    "font-weight",
    "line-height",
    "space",
    "radius",
    "shadow",
    "duration",
    "easing",
    "z",
)


def tokens(pattern: re.Pattern[str]) -> dict[str, str]:
    """Return the custom-property name to value pairs of one token block."""
    match = pattern.search(read_pjx_theme_css())
    assert match is not None, f"token block not found: {pattern.pattern}"
    return dict(DECLARATION.findall(match.group(1)))


def test_theme_path_points_at_the_shipped_sheet():
    assert PJX_THEME_PATH.name == "pjx_theme.css"
    assert PJX_THEME_PATH.is_file()


def test_the_sheet_is_package_data():
    assert files("pyjinhx.client").joinpath("pjx_theme.css").is_file()


def test_reader_returns_the_sheet_unchanged():
    css = read_pjx_theme_css()
    assert css == PJX_THEME_PATH.read_text(encoding="utf-8")
    assert css.startswith("/* pjx_theme.css")


def test_reader_decodes_the_non_ascii_comments_as_utf8():
    css = read_pjx_theme_css()
    assert "—" in css  # em dash in the header comment
    assert "·" in css  # middle dot in the breakpoint comment


def test_each_token_block_appears_once():
    css = read_pjx_theme_css()
    for block in TOKEN_BLOCKS:
        assert len(block.findall(css)) == 1, block.pattern


def test_root_defines_every_token_family():
    names = tokens(ROOT)
    assert len(names) == 90
    for family in D1_FAMILIES:
        assert any(name.startswith(f"--pjx-{family}-") for name in names), family
    for n in range(1, 9):
        assert f"--pjx-chart-series-{n}" in names


def test_override_blocks_only_redefine_root_tokens():
    root = tokens(ROOT).keys()
    media_dark = tokens(MEDIA_DARK).keys()
    for block in (MEDIA_DARK, FORCED_DARK, FORCED_LIGHT):
        names = tokens(block).keys()
        assert len(names) == 48, block.pattern
        assert names <= root, block.pattern
        assert names == media_dark, block.pattern


def test_forced_dark_matches_the_media_dark_block():
    assert tokens(FORCED_DARK) == tokens(MEDIA_DARK)


def test_forced_light_reasserts_the_root_values():
    root = tokens(ROOT)
    light = tokens(FORCED_LIGHT)
    assert light == {name: root[name] for name in light}


def test_light_brand_subtle_is_zinc_100_and_differs_from_surface_alt():
    for block in (ROOT, FORCED_LIGHT):
        light = tokens(block)
        assert light["--pjx-color-brand-subtle"] == "#f4f4f5"
        assert light["--pjx-color-brand-subtle"] != light["--pjx-color-surface-alt"]


def test_dark_brand_subtle_is_unchanged():
    for block in (MEDIA_DARK, FORCED_DARK):
        assert tokens(block)["--pjx-color-brand-subtle"] == "#09090b"


def test_breakpoints_are_a_comment_not_tokens():
    css = read_pjx_theme_css()
    assert "/* Breakpoints (documented, not tokens):" in css
    assert "--pjx-breakpoint" not in css


def test_no_custom_property_is_defined_outside_the_token_blocks():
    rest = read_pjx_theme_css()
    for block in TOKEN_BLOCKS:
        rest = block.sub("", rest)
    assert re.findall(r"--pjx-[\w-]+\s*:", rest) == []


RULE = re.compile(r"^(\.pjx-[\w-]+) \{(.*?)^\}", re.MULTILINE | re.DOTALL)
TOKEN_REFERENCE = re.compile(r"var\((--pjx-[\w-]+)\)")

SANS = "var(--pjx-font-family-sans)"
TEXT = "var(--pjx-color-text)"
MUTED = "var(--pjx-color-text-muted)"
TIGHT = "var(--pjx-line-height-tight)"
NORMAL = "var(--pjx-line-height-normal)"
REGULAR = "var(--pjx-font-weight-regular)"
SEMIBOLD = "var(--pjx-font-weight-semibold)"


def heading(size: str, weight: str) -> dict[str, str]:
    return {
        "font-family": SANS,
        "font-size": f"var(--pjx-font-size-{size})",
        "font-weight": weight,
        "line-height": TIGHT,
        "color": TEXT,
    }


def body(size: str, line_height: str, color: str = TEXT) -> dict[str, str]:
    return {
        "font-family": SANS,
        "font-size": f"var(--pjx-font-size-{size})",
        "font-weight": REGULAR,
        "line-height": line_height,
        "color": color,
    }


TYPOGRAPHY = {
    ".pjx-heading-1": heading("3xl", "var(--pjx-font-weight-bold)"),
    ".pjx-heading-2": heading("2xl", SEMIBOLD),
    ".pjx-heading-3": heading("xl", SEMIBOLD),
    ".pjx-heading-4": heading("lg", SEMIBOLD),
    ".pjx-text-lg": body("lg", "var(--pjx-line-height-relaxed)"),
    ".pjx-text": body("md", NORMAL),
    ".pjx-text-sm": body("sm", NORMAL),
    ".pjx-caption": body("xs", NORMAL, MUTED),
    ".pjx-text-muted": {"color": MUTED},
    ".pjx-text-mono": {"font-family": "var(--pjx-font-family-mono)"},
}


def typography_rules() -> list[tuple[str, dict[str, str]]]:
    """Return each top-level .pjx-* rule as (selector, property to value)."""
    return [
        (selector, dict(DECLARATION.findall(declarations)))
        for selector, declarations in RULE.findall(read_pjx_theme_css())
    ]


def test_each_typography_class_is_one_rule():
    selectors = [selector for selector, _ in typography_rules()]
    assert sorted(selectors) == sorted(TYPOGRAPHY)


def test_typography_rules_match_the_spec_table():
    assert dict(typography_rules()) == TYPOGRAPHY


def test_typography_uses_only_root_tokens():
    root = tokens(ROOT)
    for selector, declarations in typography_rules():
        for prop, value in declarations.items():
            assert not prop.startswith("--"), (selector, prop)
            reference = TOKEN_REFERENCE.fullmatch(value)
            assert reference is not None, (selector, prop, value)
            assert reference.group(1) in root, (selector, prop, value)


def test_modifiers_set_one_property_and_come_after_the_size_classes():
    rules = typography_rules()
    order = [selector for selector, _ in rules]
    declarations = dict(rules)
    assert declarations[".pjx-text-muted"] == {"color": MUTED}
    assert declarations[".pjx-text-mono"] == {
        "font-family": "var(--pjx-font-family-mono)"
    }
    last_size_class = max(
        order.index(selector)
        for selector in TYPOGRAPHY
        if selector not in (".pjx-text-muted", ".pjx-text-mono")
    )
    assert order.index(".pjx-text-muted") > last_size_class
    assert order.index(".pjx-text-mono") > last_size_class


def test_typography_follows_the_token_blocks():
    css = read_pjx_theme_css()
    assert css.index(".pjx-heading-1 {") > css.index("/* Breakpoints")
