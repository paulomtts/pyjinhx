"""Navigation builtins (tabs, breadcrumb, paginator, accordion, resizable) default to theme tokens."""

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
    "ui/pjx_breadcrumb/pjx_breadcrumb.css",
    "pjx_paginator/pjx_paginator.css",
    "ui/pjx_resizable_handle/pjx_resizable_handle.css",
    "ui/pjx_accordion_trigger/pjx_accordion_trigger.css",
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


BREADCRUMB = "pjx_breadcrumb/pjx_breadcrumb.css"


@pytest.mark.parametrize(
    ("token", "theme"),
    [
        ("--pjx-breadcrumb-sep-color", "--pjx-color-text-muted"),
        ("--pjx-breadcrumb-link-color", "--pjx-color-brand"),
        ("--pjx-breadcrumb-current-color", "--pjx-color-text"),
    ],
)
def test_breadcrumb_colours_follow_the_theme(token, theme):
    assert (
        declared(read(BREADCRUMB), ":where(:root)", token)
        == f"var({theme}, {light(theme)})"
    )


def test_breadcrumb_font_size_gains_its_fallback():
    assert (
        declared(read(BREADCRUMB), ":where(:root)", "--pjx-breadcrumb-font-size")
        == f"var(--pjx-font-size-sm, {light('--pjx-font-size-sm')})"
    )


def test_breadcrumb_gap_keeps_its_off_scale_value():
    assert (
        declared(read(BREADCRUMB), ":where(:root)", "--pjx-breadcrumb-gap") == "0.35rem"
    )


def test_breadcrumb_separator_stays_a_slash():
    assert declared(read(BREADCRUMB), ":where(:root)", "--pjx-breadcrumb-sep") == '"/"'


PAGINATOR = "pjx_paginator/pjx_paginator.css"
PAGINATOR_LINK = ".pjx-paginator__link,\n.pjx-paginator__control"


@pytest.mark.parametrize(
    ("token", "theme"),
    [
        ("--pjx-paginator-link-fg", "--pjx-color-text"),
        ("--pjx-paginator-current-bg", "--pjx-color-brand"),
        ("--pjx-paginator-border", "--pjx-color-border"),
        ("--pjx-paginator-radius", "--pjx-radius-sm"),
        ("--pjx-paginator-gap", "--pjx-space-1"),
    ],
)
def test_paginator_tokens_default_to_theme_tokens(token, theme):
    assert (
        declared(read_builtin(PAGINATOR), ":where(:root)", token)
        == f"var({theme}, {light(theme)})"
    )


def test_paginator_current_page_text_is_on_brand():
    # on-brand, not surface: it is the text colour paired with the brand fill.
    assert (
        declared(read_builtin(PAGINATOR), ":where(:root)", "--pjx-paginator-current-fg")
        == f"var(--pjx-color-on-brand, {light('--pjx-color-on-brand')})"
    )


def test_paginator_hover_mixes_the_theme_surfaces():
    surface = light("--pjx-color-surface")
    surface_alt = light("--pjx-color-surface-alt")
    assert declared(
        read_builtin(PAGINATOR), ":where(:root)", "--pjx-paginator-link-hover-bg"
    ) == (
        f"color-mix(in srgb, var(--pjx-color-surface, {surface}) 40%, "
        f"var(--pjx-color-surface-alt, {surface_alt}))"
    )


def test_paginator_font_size_transition_and_ellipsis():
    css = read_builtin(PAGINATOR)
    assert (
        declared(css, ".pjx-paginator", "font-size")
        == f"var(--pjx-font-size-sm, {light('--pjx-font-size-sm')})"
    )
    assert declared(css, PAGINATOR_LINK, "transition") == f"background {motion()}"
    assert (
        declared(css, ".pjx-paginator__ellipsis", "color")
        == f"var(--pjx-color-text-muted, {light('--pjx-color-text-muted')})"
    )


def test_paginator_keeps_its_off_scale_padding():
    css = read_builtin(PAGINATOR)
    assert declared(css, PAGINATOR_LINK, "padding") == "0.35rem 0.6rem"
    assert declared(css, ".pjx-paginator__ellipsis", "padding") == "0.35rem 0.3rem"
    assert declared(css, PAGINATOR_LINK, "min-width") == "2rem"
    assert declared(css, ".pjx-paginator__ellipsis", "min-width") == "2rem"


def test_paginator_current_page_reads_its_component_tokens():
    css = read_builtin(PAGINATOR)
    selector = ".pjx-paginator__link--current"
    assert declared(css, selector, "color") == "var(--pjx-paginator-current-fg)"
    assert declared(css, selector, "background") == "var(--pjx-paginator-current-bg)"
    assert declared(css, selector, "border-color") == "var(--pjx-paginator-current-bg)"


HANDLE = "pjx_resizable_handle/pjx_resizable_handle.css"
HANDLE_ACTIVE = (
    ".pjx-resizable-group__handle:hover::before,\n"
    ".pjx-resizable-group--dragging .pjx-resizable-group__handle::before"
)


def test_resizable_handle_size_is_on_the_spacing_scale():
    assert declared(read(HANDLE), ".pjx-resizable-group__handle", "flex") == (
        "0 0 var(--pjx-resizable-handle-size, "
        f"var(--pjx-space-2, {light('--pjx-space-2')}))"
    )


def test_resizable_grip_defaults_to_theme_tokens():
    css = read(HANDLE)
    grip = ".pjx-resizable-group__handle::before"
    assert declared(css, grip, "background") == (
        "var(--pjx-resizable-grip-color, "
        f"var(--pjx-color-border, {light('--pjx-color-border')}))"
    )
    assert (
        declared(css, grip, "border-radius")
        == f"var(--pjx-radius-full, {light('--pjx-radius-full')})"
    )


def test_resizable_grip_transition_uses_theme_motion():
    assert (
        declared(read(HANDLE), ".pjx-resizable-group__handle::before", "transition")
        == f"background {motion()}"
    )


def test_resizable_active_grip_defaults_to_brand_muted():
    # One rule for both selectors: the pointer leaves the handle mid-drag.
    assert declared(read(HANDLE), HANDLE_ACTIVE, "background") == (
        "var(--pjx-resizable-handle-color-active, "
        f"var(--pjx-color-brand-muted, {light('--pjx-color-brand-muted')}))"
    )


def test_resizable_focus_ring_uses_brand_muted():
    css = read(HANDLE)
    focus = ".pjx-resizable-group__handle:focus-visible"
    assert (
        declared(css, focus, "outline")
        == f"2px solid var(--pjx-color-brand-muted, {light('--pjx-color-brand-muted')})"
    )
    assert declared(css, focus, "outline-offset") == "-2px"


def test_resizable_grip_keeps_its_literal_sizes():
    css = read(HANDLE)
    row = ".pjx-resizable-group--row > .pjx-resizable-group__handle::before"
    column = ".pjx-resizable-group--column > .pjx-resizable-group__handle::before"
    assert declared(css, row, "width") == "3px"
    assert declared(css, row, "height") == "2.5rem"
    assert declared(css, column, "width") == "2.5rem"
    assert declared(css, column, "height") == "3px"
    # Off-scale values stay literal with a comment saying why (DT:66).
    assert any("grip" in comment for comment in COMMENT.findall(css))


TRIGGER = "pjx_accordion_trigger/pjx_accordion_trigger.css"
REDUCED_MOTION = re.compile(
    r"@media \(prefers-reduced-motion: reduce\) \{(.*?)^\}", re.MULTILINE | re.DOTALL
)


def test_accordion_trigger_spacing_is_on_the_scale():
    css = read(TRIGGER)
    space_1 = f"var(--pjx-space-1, {light('--pjx-space-1')})"
    space_2 = f"var(--pjx-space-2, {light('--pjx-space-2')})"
    space_3 = f"var(--pjx-space-3, {light('--pjx-space-3')})"
    assert declared(css, ".pjx-accordion__trigger", "gap") == space_2
    assert (
        declared(css, ".pjx-accordion__trigger", "padding")
        == f"var(--pjx-accordion-trigger-padding, {space_2} {space_3})"
    )
    assert (
        declared(css, ".pjx-accordion__actions", "gap")
        == f"var(--pjx-accordion-actions-gap, {space_1})"
    )


def test_accordion_trigger_font_weight_is_medium():
    assert declared(read(TRIGGER), ".pjx-accordion__trigger", "font-weight") == (
        "var(--pjx-accordion-trigger-font-weight, "
        f"var(--pjx-font-weight-medium, {light('--pjx-font-weight-medium')}))"
    )


def test_accordion_chevron_uses_theme_motion_and_respects_reduced_motion():
    css = read(TRIGGER)
    assert (
        declared(css, ".pjx-accordion__chevron", "transition")
        == f"transform {motion()}"
    )
    media = REDUCED_MOTION.search(css)
    assert media is not None, "reduced-motion block removed"
    assert ".pjx-accordion__chevron" in media.group(1)
    assert "transition: none;" in media.group(1)
