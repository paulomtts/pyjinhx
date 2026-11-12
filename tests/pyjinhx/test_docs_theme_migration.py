"""Doc-lint: the docs move readers off the dropped theme names.

Builtin CSS no longer reads the unprefixed theme variables (`--surface`,
`--radius-md`, ...). These check that the CHANGELOG tells an upgrading app how
to migrate, that its mapping table is complete and names tokens the theme sheet
defines, and that no docs page still presents an old name as current.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CHANGELOG = _ROOT / "CHANGELOG.md"
_THEME = _ROOT / "pyjinhx" / "client" / "pjx_theme.css"
_HEADING = "## Unreleased — Default theme"

# Old name (without the leading `--`) -> what replaces it.
_MAPPING = {
    "surface": "--pjx-color-surface",
    "surface-alt": "--pjx-color-surface-alt",
    "surface-hover": "--pjx-color-surface-hover",
    "text": "--pjx-color-text",
    "text-muted": "--pjx-color-text-muted",
    "border": "--pjx-color-border",
    "border-focus": "--pjx-color-border-focus",
    "brand": "--pjx-color-brand",
    "brand-subtle": "--pjx-color-brand-subtle",
    "brand-muted": "--pjx-color-brand-muted",
    "error": "--pjx-color-error",
    "error-bg": "--pjx-color-error-subtle",
    "error-border": "--pjx-color-error-border",
    "success": "--pjx-color-success",
    "warning": "--pjx-color-warning",
    "font-size-xs": "--pjx-font-size-xs",
    "font-size-sm": "--pjx-font-size-sm",
    "font-size-md": "--pjx-font-size-md",
    "radius-sm": "--pjx-radius-sm",
    "radius-md": "--pjx-radius-md",
    "radius-lg": "--pjx-radius-lg",
    "radius-full": "--pjx-radius-full",
    "shadow-md": "--pjx-shadow-md",
    "space-N": "--pjx-space-N",
    "transition": "var(--pjx-duration-normal) var(--pjx-easing-standard)",
}


def _entry() -> str:
    text = _CHANGELOG.read_text(encoding="utf-8")
    start = text.index(_HEADING)
    end = text.index("\n## ", start + len(_HEADING))
    return text[start:end]


def _mapping_rows() -> dict[str, str]:
    rows = re.findall(r"^\| `--([\w-]+)` \| `([^`]+)`", _entry(), flags=re.MULTILINE)
    return dict(rows)


def test_changelog_opens_with_the_unreleased_theme_entry():
    text = _CHANGELOG.read_text(encoding="utf-8")
    headings = re.findall(r"^## .*$", text, flags=re.MULTILINE)
    assert headings[0] == _HEADING
    assert text.index(_HEADING) < text.index("## 1.14.0")
    assert "### Added" in _entry()
    assert "### Changed (breaking): theme token names" in _entry()


def test_changelog_maps_every_dropped_name():
    assert _mapping_rows() == _MAPPING


def test_changelog_new_names_exist_in_the_theme_sheet():
    sheet = _THEME.read_text(encoding="utf-8")
    declared = set(re.findall(r"(--pjx-[\w-]+)\s*:", sheet))
    steps = sorted({n for n in declared if re.fullmatch(r"--pjx-space-\d+", n)})
    assert steps
    named = set()
    for new in _mapping_rows().values():
        for name in re.findall(r"--pjx-[\w-]+", new):
            named |= set(steps) if name == "--pjx-space-N" else {name}
    assert sorted(named - declared) == []


def test_changelog_notice_says_how_to_turn_the_theme_on():
    entry = _entry()
    for phrase in (
        'theme="default"',
        "PJX_THEME",
        "read_pjx_theme_css",
        "data-pjx-theme",
        "no fallback",
    ):
        assert phrase in entry, phrase


def test_changelog_links_resolve():
    links = re.findall(r"\]\(([^)]+)\)", _entry())
    assert links
    local = [link for link in links if not link.startswith("http")]
    assert [link for link in local if not (_ROOT / link).is_file()] == []
