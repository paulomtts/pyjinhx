"""Doc-lint: the theming guide matches the shipped theme sheet.

The guide names tokens, breakpoints and selectors by hand, so these check
them against the CSS that actually ships.
"""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_GUIDE = _ROOT / "docs" / "guide" / "theming.md"
_SHEET = _ROOT / "pyjinhx" / "client" / "pjx_theme.css"
# Lookahead skips family names written as `--pjx-color-*` or `--pjx-chart-series-N`.
_TOKEN = re.compile(r"--pjx-[a-z0-9]+(?:-[a-z0-9]+)*(?![-\w*])")
_DOCS = _ROOT / "docs"
# One typography rule from the sheet: selector, then its declarations.
_TYPOGRAPHY_RULE = re.compile(
    r"^(\.pjx-[a-z0-9-]+) \{(.*?)^\}", re.MULTILINE | re.DOTALL
)
_DARK_SELECTORS = (
    ':root:not([data-pjx-theme="light"])',
    '[data-pjx-theme="dark"]',
    '[data-pjx-theme="light"]',
)


def _guide() -> str:
    return _GUIDE.read_text(encoding="utf-8")


def _sheet() -> str:
    return _SHEET.read_text(encoding="utf-8")


def _all_css() -> str:
    builtins = sorted((_ROOT / "pyjinhx" / "builtins").rglob("*.css"))
    return _sheet() + "".join(p.read_text(encoding="utf-8") for p in builtins)


def _typography_section() -> str:
    return _guide().split("## Typography\n", 1)[1].split("\n## ", 1)[0]


def _typography_rules() -> list[tuple[str, str]]:
    sheet = _sheet()
    return _TYPOGRAPHY_RULE.findall(sheet[sheet.index("/* Typography") :])


def test_guide_is_in_nav():
    assert _GUIDE.is_file()
    assert "guide/theming.md" in (_ROOT / "mkdocs.yml").read_text(encoding="utf-8")


def test_named_tokens_exist():
    css = _all_css()
    named = set(_TOKEN.findall(_guide()))
    assert named
    missing = {n for n in named if not re.search(re.escape(n) + r"\s*:", css)}
    assert not missing, f"guide names undefined tokens: {sorted(missing)}"


def test_breakpoints_match_sheet():
    comment = re.search(r"/\*\s*Breakpoints.*?\*/", _sheet())
    assert comment
    widths = re.findall(r"\d+px", comment.group(0))
    assert len(widths) == 4
    guide = _guide()
    assert all(w in guide for w in widths), widths


def test_dark_selectors_match_sheet():
    guide, sheet = _guide(), _sheet()
    for selector in _DARK_SELECTORS:
        assert selector in guide, selector
        assert selector in sheet, selector


def test_override_pattern_is_in_order():
    # The order is what makes the pattern correct: forced-light must come last
    # so a light wrapper inside a dark page wins.
    guide = _guide()
    # [^`]* keeps the match inside one fence; the one-line `:root` example
    # before it has no @media, so only the four-rule block matches.
    block = re.search(r"```css\n(:root \{ --pjx-color-brand[^`]*@media[^`]*)```", guide)
    assert block
    text = block.group(1)
    positions = [
        text.index(":root {"),
        text.index("@media (prefers-color-scheme: dark)"),
        text.index('[data-pjx-theme="dark"] {'),
        text.index('[data-pjx-theme="light"] {'),
    ]
    assert positions == sorted(positions)


def test_wrapper_limit_is_stated():
    # Component tokens resolve at :root, so a wrapper's theme tokens do not
    # reach builtins; the guide has to say that rather than promise it.
    assert ":where(:root)" in _guide()
    assert ":where(:root)" in (
        _ROOT / "pyjinhx" / "builtins" / "pjx_paginator" / "pjx_paginator.css"
    ).read_text(encoding="utf-8")


def test_pitfalls_are_named():
    guide = _guide()
    assert "ValueError" in guide
    assert "PJX_THEME" in guide
    assert '<style id="pjx-theme">' in guide
    assert "partial" in guide


def test_configuration_links_to_guide():
    configuration = (_ROOT / "docs" / "guide" / "configuration.md").read_text(
        encoding="utf-8"
    )
    bullet = next(
        line for line in configuration.splitlines() if line.startswith("- `PJX_THEME`")
    )
    assert "(theming.md)" in bullet


def test_typography_classes_are_tabled():
    rules = _typography_rules()
    assert len(rules) == 10
    lines = _guide().splitlines()
    rows = []
    for selector, declarations in rules:
        prefix = f"| `{selector}` |"
        row = next((i for i, line in enumerate(lines) if line.startswith(prefix)), None)
        assert row is not None, f"no table row for {selector}"
        # Equal, not a subset: a row naming a token the class does not set is wrong too.
        used = set(re.findall(r"var\((--pjx-[a-z0-9-]+)\)", declarations))
        assert set(_TOKEN.findall(lines[row])) == used, selector
        rows.append(row)
    assert rows == sorted(rows), "rows are not in sheet order"


def test_typography_demo_is_in_guide():
    sys.path.insert(0, str(_DOCS))
    from demos import DEMOS

    assert "<!-- demo: Typography -->" in _typography_section()
    assert "Typography" in DEMOS


def test_typography_marker_resolves_from_the_guide():
    sys.path.insert(0, str(_DOCS))
    import hooks

    class Page:
        class file:
            src_path = "guide/theming.md"

        url = "guide/theming/"

    out = hooks.on_page_markdown(
        "<!-- demo: Typography -->", page=Page(), config={}, files=None
    )
    assert '<iframe src="../../demos/typography.html"' in out


def test_caption_is_said_to_be_muted():
    section = _typography_section()
    assert any(
        ".pjx-caption" in line and ".pjx-text-muted" in line and "muted" in line
        for line in section.splitlines()
        if not line.startswith("|")
    ), "the text must say .pjx-caption is already muted"
    assert "pjx-text-sm pjx-text-muted" in section
    assert "margin" in section
    assert "(../reference/theme-tokens.md)" in section
