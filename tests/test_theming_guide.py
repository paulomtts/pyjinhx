"""Doc-lint: the theming guide matches the shipped theme sheet.

The guide names tokens, breakpoints and selectors by hand, so these check
them against the CSS that actually ships.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_GUIDE = _ROOT / "docs" / "guide" / "theming.md"
_SHEET = _ROOT / "pyjinhx" / "client" / "pjx_theme.css"
# Lookahead skips family names written as `--pjx-color-*` or `--pjx-chart-series-N`.
_TOKEN = re.compile(r"--pjx-[a-z0-9]+(?:-[a-z0-9]+)*(?![-\w*])")
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
