"""Navigation builtins (tabs, breadcrumb, paginator) default to theme tokens."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pyjinhx.client import read_pjx_theme_css

UI = Path(__file__).parents[3] / "pyjinhx" / "builtins" / "ui"
BUILTINS = UI.parent

# Copied from tests/pyjinhx/builtins/test_feedback_theme_tokens.py: the tests
# tree has no __init__.py files, so test modules cannot import each other reliably.
ROOT = re.compile(r"^:root \{(.*?)^\}", re.MULTILINE | re.DOTALL)
DECLARATION = re.compile(r"([\w-]+):\s*([^;]+);")
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

# A hex colour is allowed only as the fallback of a theme colour token.
FALLBACK_HEX = re.compile(r"var\(--pjx-color-[\w-]+,\s*#[0-9a-fA-F]{3,8}\)")
BARE_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# Paths relative to pyjinhx/builtins; one line per migrated stylesheet.
NAVIGATION_SHEETS = [
    "ui/pjx_tab_group/pjx_tab_group.css",
    "ui/pjx_tab/pjx_tab.css",
]


def light(token: str) -> str:
    """Return token's value in the theme sheet's light :root block."""
    match = ROOT.search(read_pjx_theme_css())
    assert match is not None, f"token block not found: {ROOT.pattern}"
    return dict(DECLARATION.findall(match.group(1)))[token]


def read(path: str) -> str:
    return (UI / path).read_text(encoding="utf-8")


def read_builtin(path: str) -> str:
    return (BUILTINS / path).read_text(encoding="utf-8")


def rule_block(css: str, selector: str) -> str:
    """Return the body of the rule whose selector starts a line, comments removed."""
    css = COMMENT.sub("", css)
    pattern = rf"^{re.escape(selector)}\s*\{{([^}}]*)\}}"
    match = re.search(pattern, css, re.MULTILINE)
    assert match is not None, f"no {selector} rule"
    return match.group(1)


def declared(css: str, selector: str, prop: str) -> str:
    """Return prop's value inside selector's rule, whitespace collapsed."""
    block = rule_block(css, selector)
    match = re.search(rf"(?<![\w-]){re.escape(prop)}:\s*([^;]+);", block)
    assert match is not None, f"{selector} does not declare {prop}"
    return " ".join(match.group(1).split())


def motion() -> str:
    """Return the theme's standard duration-and-easing pair, with fallbacks."""
    duration = light("--pjx-duration-normal")
    easing = light("--pjx-easing-standard")
    return (
        f"var(--pjx-duration-normal, {duration}) var(--pjx-easing-standard, {easing})"
    )


@pytest.mark.parametrize("path", NAVIGATION_SHEETS)
def test_no_bare_hex_colours_outside_fallbacks(path):
    css = FALLBACK_HEX.sub("", read_builtin(path))
    assert not BARE_HEX.findall(css), f"{path} hard-codes a colour outside a fallback"


TAB_GROUP = "pjx_tab_group/pjx_tab_group.css"


@pytest.mark.parametrize(
    ("token", "theme"),
    [
        ("--pjx-tab-group-border", "--pjx-color-border"),
        ("--pjx-tab-group-bg", "--pjx-color-surface-alt"),
        ("--pjx-tab-group-tab-fg", "--pjx-color-text-muted"),
        ("--pjx-tab-group-tab-active-fg", "--pjx-color-text"),
        ("--pjx-tab-group-tab-active-border", "--pjx-color-brand"),
        ("--pjx-tab-group-panel-bg", "--pjx-color-surface"),
        ("--pjx-tab-group-radius", "--pjx-radius-md"),
    ],
)
def test_tab_group_tokens_default_to_theme_tokens(token, theme):
    assert (
        declared(read(TAB_GROUP), ":where(:root)", token)
        == f"var({theme}, {light(theme)})"
    )


def test_tab_group_padding_is_on_the_spacing_scale():
    assert (
        declared(read(TAB_GROUP), ":where(:root)", "--pjx-tab-group-padding")
        == f"var(--pjx-space-4, {light('--pjx-space-4')})"
    )


def test_tab_group_rule_reads_its_component_tokens():
    css = read(TAB_GROUP)
    assert (
        declared(css, ".pjx-tab-group", "border")
        == "1px solid var(--pjx-tab-group-border)"
    )
    assert (
        declared(css, ".pjx-tab-group", "border-radius")
        == "var(--pjx-tab-group-radius)"
    )
    assert (
        declared(css, ".pjx-tab-group", "background") == "var(--pjx-tab-group-panel-bg)"
    )


TAB = "pjx_tab/pjx_tab.css"


def test_tab_font_size_is_the_small_step():
    assert (
        declared(read(TAB), ".pjx-tab", "font-size")
        == f"var(--pjx-font-size-sm, {light('--pjx-font-size-sm')})"
    )


def test_tab_transition_uses_theme_motion():
    m = motion()
    assert (
        declared(read(TAB), ".pjx-tab", "transition")
        == f"color {m}, border-color {m}, background {m}"
    )


@pytest.mark.parametrize(
    "selector", [".pjx-tab:hover", '.pjx-tab[aria-current="true"]']
)
def test_tab_pressed_backgrounds_mix_the_theme_surface(selector):
    surface = light("--pjx-color-surface")
    assert declared(read(TAB), selector, "background") == (
        f"color-mix(in srgb, var(--pjx-color-surface, {surface}) 35%, "
        "var(--pjx-tab-group-bg))"
    )


@pytest.mark.parametrize(
    "selector", ['.pjx-tab[aria-current="true"]', ".pjx-tab__close"]
)
def test_tab_corners_use_the_small_radius(selector):
    assert (
        declared(read(TAB), selector, "border-radius")
        == f"var(--pjx-radius-sm, {light('--pjx-radius-sm')})"
    )


def test_tab_close_hover_tints_the_theme_text():
    text = light("--pjx-color-text")
    assert declared(read(TAB), ".pjx-tab__close:hover", "background") == (
        f"color-mix(in srgb, var(--pjx-color-text, {text}) 12%, transparent)"
    )


def test_tab_keeps_its_off_scale_spacing():
    css = read(TAB)
    assert declared(css, ".pjx-tab", "gap") == "0.4rem"
    assert declared(css, ".pjx-tab", "padding") == "0.55rem 1.1rem"
    assert declared(css, ".pjx-tab__close", "margin-left") == "0.15rem"
    assert declared(css, ".pjx-tab__close", "padding") == "0 0.2rem"
    # Relative glyph sizing, not a theme value.
    assert declared(css, ".pjx-tab__close", "font-size") == "1.15em"


def test_tab_focus_and_underline_read_the_component_token():
    css = read(TAB)
    assert (
        declared(css, ".pjx-tab:focus-visible", "outline")
        == "2px solid var(--pjx-tab-group-tab-active-border)"
    )
    assert (
        declared(css, ".pjx-tab-group__list .pjx-tab--selected", "border-bottom-color")
        == "var(--pjx-tab-group-tab-active-border)"
    )
