"""Migrated stylesheets use only defined theme tokens, with light-value fallbacks."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pyjinhx.client import read_pjx_theme_css

REPO_ROOT = Path(__file__).parents[2]
THEME_SHEET = "pyjinhx/client/pjx_theme.css"

# Copied from tests/pyjinhx/client/test_pjx_theme.py: the tests tree has no
# __init__.py files, so test modules cannot import each other reliably.
ROOT = re.compile(r"^:root \{(.*?)^\}", re.MULTILINE | re.DOTALL)
DECLARATION = re.compile(r"([\w-]+):\s*([^;]+);")

# chart-series takes only a numeric suffix: pjx_chart.css has a component
# token --pjx-chart-series-color that must not count as a theme token.
THEME_TOKEN = re.compile(
    r"(?<![\w-])--pjx-(?:"
    r"(?:color|font-family|font-size|font-weight|line-height|space|radius"
    r"|shadow|duration|easing|z)-[\w-]+"
    r"|chart-series-\d+(?![\w-])"
    r")"
)
LEGACY_NAME = re.compile(
    r"(?<![\w-])--(?:"
    r"surface(?:-alt|-hover)?|text(?:-muted)?|border(?:-focus)?"
    r"|brand(?:-subtle|-muted)?|error(?:-bg|-border)?|success|warning"
    r"|font-size-[\w-]+|radius-[\w-]+|shadow-md|space-\d+|transition"
    r")(?![\w-])"
)
VAR_OPEN = re.compile(r"(?<![\w-])var\(")

# Stylesheets that still use legacy names. Remove a path once its file is
# migrated; the suite fails until you do.
LEGACY_PENDING: tuple[str, ...] = (
    "pyjinhx/builtins/pjx_page_loader/pjx_page_loader.css",
    "pyjinhx/builtins/pjx_paginator/pjx_paginator.css",
    "pyjinhx/builtins/pjx_region_loader/pjx_region_loader.css",
    "pyjinhx/builtins/pjx_table/pjx_table.css",
    "pyjinhx/builtins/ui/pjx_alert/pjx_alert.css",
    "pyjinhx/builtins/ui/pjx_avatar/pjx_avatar.css",
    "pyjinhx/builtins/ui/pjx_avatar_stack/pjx_avatar_stack.css",
    "pyjinhx/builtins/ui/pjx_badge/pjx_badge.css",
    "pyjinhx/builtins/ui/pjx_breadcrumb/pjx_breadcrumb.css",
    "pyjinhx/builtins/ui/pjx_card/pjx_card.css",
    "pyjinhx/builtins/ui/pjx_card_header/pjx_card_header.css",
    "pyjinhx/builtins/ui/pjx_carousel/pjx_carousel.css",
    "pyjinhx/builtins/ui/pjx_chart/pjx_chart.css",
    "pyjinhx/builtins/ui/pjx_chip_input/pjx_chip_input.css",
    "pyjinhx/builtins/ui/pjx_divider/pjx_divider.css",
    "pyjinhx/builtins/ui/pjx_empty_state/pjx_empty_state.css",
    "pyjinhx/builtins/ui/pjx_form_field/pjx_form_field.css",
    "pyjinhx/builtins/ui/pjx_graph/pjx_graph.css",
    "pyjinhx/builtins/ui/pjx_graph_controls/pjx_graph_controls.css",
    "pyjinhx/builtins/ui/pjx_graph_node/pjx_graph_node.css",
    "pyjinhx/builtins/ui/pjx_graph_side_panel/pjx_graph_side_panel.css",
    "pyjinhx/builtins/ui/pjx_notification/pjx_notification.css",
    "pyjinhx/builtins/ui/pjx_password_input/pjx_password_input.css",
    "pyjinhx/builtins/ui/pjx_progress/pjx_progress.css",
    "pyjinhx/builtins/ui/pjx_resizable_handle/pjx_resizable_handle.css",
    "pyjinhx/builtins/ui/pjx_roster_picker/pjx_roster_picker.css",
    "pyjinhx/builtins/ui/pjx_segmented_control/pjx_segmented_control.css",
    "pyjinhx/builtins/ui/pjx_select/pjx_select.css",
    "pyjinhx/builtins/ui/pjx_skeleton/pjx_skeleton.css",
    "pyjinhx/builtins/ui/pjx_spinner/pjx_spinner.css",
    "pyjinhx/builtins/ui/pjx_tab/pjx_tab.css",
    "pyjinhx/builtins/ui/pjx_tab_group/pjx_tab_group.css",
    "pyjinhx/builtins/ui/pjx_toast_host/pjx_toast_host.css",
    "pyjinhx/builtins/ui/pjx_toggle_switch/pjx_toggle_switch.css",
)


def light_values() -> dict[str, str]:
    """Return the custom-property values declared in the sheet's :root block."""
    match = ROOT.search(read_pjx_theme_css())
    assert match is not None, f"token block not found: {ROOT.pattern}"
    return dict(DECLARATION.findall(match.group(1)))


def theme_tokens(css: str) -> set[str]:
    """Return every theme-token name in css, in var() uses and declarations."""
    return set(THEME_TOKEN.findall(css))


def legacy_names(css: str) -> set[str]:
    """Return every legacy custom-property name in css, comments included."""
    return set(LEGACY_NAME.findall(css))


def var_references(css: str) -> list[tuple[str, str | None]]:
    """Return (name, fallback) for every var() in css, nested ones included.

    The fallback is everything after the first top-level comma, or None when
    there is no comma.
    """
    references = []
    for match in VAR_OPEN.finditer(css):
        start = match.end()
        depth = 0
        comma = None
        end = len(css)
        for index in range(start, len(css)):
            char = css[index]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    end = index
                    break
                depth -= 1
            elif char == "," and depth == 0 and comma is None:
                comma = index
        if comma is None:
            references.append((css[start:end].strip(), None))
        else:
            references.append((css[start:comma].strip(), css[comma + 1 : end].strip()))
    return references


def squash(value: str) -> str:
    """Trim value and collapse each run of whitespace into one space."""
    return " ".join(value.split())


def undefined_tokens(css: str, light: dict[str, str]) -> set[str]:
    """Return the theme tokens in css that the sheet's :root does not declare."""
    return {name for name in theme_tokens(css) if name not in light}


def fallback_mismatches(css: str, light: dict[str, str]) -> list[str]:
    """Describe each theme-token var() whose fallback is not the light value."""
    problems = []
    for name, fallback in var_references(css):
        # Undefined tokens have no light value to compare; undefined_tokens reports them.
        if not THEME_TOKEN.fullmatch(name) or name not in light:
            continue
        expected = light[name]
        if fallback is None or squash(fallback) != squash(expected):
            found = "none" if fallback is None else fallback
            problems.append(f"{name}: fallback {found}, expected {expected}")
    return problems


def stylesheets() -> list[str]:
    """Return the repo-relative paths of every pyjinhx stylesheet but the theme sheet."""
    paths = (
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "pyjinhx").rglob("*.css")
    )
    return sorted(path for path in paths if path != THEME_SHEET)


STYLESHEETS = stylesheets()
MIGRATED = [path for path in STYLESHEETS if path not in LEGACY_PENDING]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_sheet_light_values_parse():
    light = light_values()
    assert light
    assert light["--pjx-color-surface"] == "#ffffff"
    assert light["--pjx-color-brand"] == "#27272a"


@pytest.mark.parametrize("path", MIGRATED)
def test_migrated_stylesheet_tokens_are_defined(path):
    undefined = undefined_tokens(read(path), light_values())
    assert not undefined, f"{path} uses undefined theme tokens: {sorted(undefined)}"


@pytest.mark.parametrize("path", MIGRATED)
def test_migrated_stylesheet_fallbacks_match_light_values(path):
    problems = fallback_mismatches(read(path), light_values())
    assert not problems, f"{path}: " + "; ".join(problems)


@pytest.mark.parametrize("path", MIGRATED)
def test_migrated_stylesheet_has_no_legacy_names(path):
    found = legacy_names(read(path))
    assert not found, f"{path} still uses legacy names: {sorted(found)}"


def test_pending_list_is_sorted_and_unique():
    assert LEGACY_PENDING == tuple(sorted(set(LEGACY_PENDING)))


@pytest.mark.parametrize("path", LEGACY_PENDING)
def test_pending_path_still_needs_migration(path):
    assert (REPO_ROOT / path).is_file(), f"pending path does not exist: {path}"
    assert path in STYLESHEETS, f"{path} is not a stylesheet under test"
    assert legacy_names(read(path)), (
        f"{path} has no legacy names left; remove it from LEGACY_PENDING"
    )


def test_theme_token_finder_matches_only_theme_families():
    css = (
        "--pjx-color-surface --pjx-font-family-sans --pjx-z-overlay "
        "--pjx-chart-series-3 --pjx-chart-series-color --pjx-badge-font-size "
        "--pjx-chart-1 --pjx-drawer-z"
    )
    assert theme_tokens(css) == {
        "--pjx-color-surface",
        "--pjx-font-family-sans",
        "--pjx-z-overlay",
        "--pjx-chart-series-3",
    }


def test_legacy_finder_matches_whole_mapped_names_anywhere():
    css = (
        "a { color: var(--surface); border-color: var(--text-muted); "
        "border-radius: var(--radius-full); gap: calc(var(--space-3)*2); "
        "transition: var(--transition); }\n"
        ":root { --surface: #fff; }\n"
        "/* was --brand-subtle */\n"
        "b { color: var(--text-subtle); width: var(--border-width); "
        "fill: var(--pjx-color-text); background: var(--accent-soft); "
        "outline-color: var(--danger); }"
    )
    assert legacy_names(css) == {
        "--surface",
        "--text-muted",
        "--radius-full",
        "--space-3",
        "--transition",
        "--brand-subtle",
    }


def test_var_scanner_reads_names_and_fallbacks():
    assert var_references("var(--pjx-color-surface, #ffffff)") == [
        ("--pjx-color-surface", "#ffffff")
    ]
    assert var_references("var(--pjx-color-surface)") == [("--pjx-color-surface", None)]
    assert var_references("var( --pjx-color-surface ,  #ffffff )") == [
        ("--pjx-color-surface", "#ffffff")
    ]
    stack = 'system-ui, -apple-system, "Segoe UI", sans-serif'
    assert var_references(f"var(--pjx-font-family-sans, {stack})") == [
        ("--pjx-font-family-sans", stack)
    ]
    assert var_references("var(--pjx-easing-standard, cubic-bezier(0.2, 0, 0, 1))") == [
        ("--pjx-easing-standard", "cubic-bezier(0.2, 0, 0, 1)")
    ]
    assert var_references("var(--pjx-button-bg, var(--pjx-color-brand, #27272a))") == [
        ("--pjx-button-bg", "var(--pjx-color-brand, #27272a)"),
        ("--pjx-color-brand", "#27272a"),
    ]
    assert var_references("z-index: calc(var(--pjx-z-tooltip, 400) - 10);") == [
        ("--pjx-z-tooltip", "400")
    ]


def test_var_scanner_tolerates_an_unclosed_var():
    assert var_references("color: var(--pjx-color-text, #18181b") == [
        ("--pjx-color-text", "#18181b")
    ]


def test_fallback_check_reports_each_bad_reference():
    light = {
        "--pjx-color-surface": "#ffffff",
        "--pjx-font-family-sans": "system-ui, sans-serif",
    }
    css = (
        "a { color: var(--pjx-color-surface, #fff); }\n"
        "b { color: var(--pjx-color-surface); }\n"
        "c { color: var(--pjx-color-surface, #FFFFFF); }\n"
        "d { color: var(--pjx-color-surface,  #ffffff ); }\n"
        "e { font-family: var(--pjx-font-family-sans, system-ui,\n    sans-serif); }\n"
        "f { color: var(--pjx-color-made-up, red); --pjx-space-99: 1px; }\n"
    )
    assert fallback_mismatches(css, light) == [
        "--pjx-color-surface: fallback #fff, expected #ffffff",
        "--pjx-color-surface: fallback none, expected #ffffff",
        "--pjx-color-surface: fallback #FFFFFF, expected #ffffff",
    ]
    assert undefined_tokens(css, light) == {"--pjx-color-made-up", "--pjx-space-99"}


def test_fallback_check_passes_a_correct_reference():
    light = {"--pjx-color-brand": "#27272a"}
    css = "a { color: var(--pjx-button-bg, var(--pjx-color-brand, #27272a)); }"
    assert fallback_mismatches(css, light) == []
    assert undefined_tokens(css, light) == set()
