"""The theme token reference page is generated from, and matches, the shipped sheet.

The table comes from docs/hooks.py at build time. These tests read the sheet
with their own parsing (not the hook's), so a generator bug cannot hide itself.
"""

import re
import sys
from pathlib import Path

import pytest

import pyjinhx.builtins  # noqa: F401

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs"
_SHEET = _ROOT / "pyjinhx" / "client" / "pjx_theme.css"
sys.path.insert(0, str(_DOCS))

import hooks

_HEADER = "| Token | Light | Dark |"
_SEPARATOR = "|---|---|---|"
_DECLARATION = re.compile(r"(--pjx-[a-z0-9-]+)\s*:\s*([^;]+);")


def _sheet() -> str:
    return _SHEET.read_text(encoding="utf-8")


def _declarations(css: str, opener: str, closer: str) -> list[tuple[str, str]]:
    # Slice by plain string search rather than the hook's regex, so the two
    # readings of the sheet are independent.
    start = css.index(opener) + len(opener)
    end = css.index(closer, start)
    return [(n, v.strip()) for n, v in _DECLARATION.findall(css[start:end])]


def _root_tokens() -> list[tuple[str, str]]:
    return _declarations(_sheet(), "\n:root {", "\n}")


def _forced_dark_tokens() -> dict[str, str]:
    return dict(_declarations(_sheet(), '\n[data-pjx-theme="dark"] {', "\n}"))


def _media_dark_tokens() -> dict[str, str]:
    opener = '\n  :root:not([data-pjx-theme="light"]) {'
    return dict(_declarations(_sheet(), opener, "\n  }"))


def _rows(table: str) -> list[list[str]]:
    lines = table.splitlines()
    assert lines[:2] == [_HEADER, _SEPARATOR]
    # Split on pipes not escaped as \| ; drop the empty edges outside the outer pipes.
    return [
        [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        for line in lines[2:]
    ]


def _real_rows() -> list[list[str]]:
    return _rows(hooks.theme_token_table(_sheet()))


def _code(text: str) -> str:
    return f"`{text}`"


def test_table_lists_every_root_token_in_order():
    tokens = [row[0] for row in _real_rows()]
    expected = [_code(name) for name, _ in _root_tokens()]
    assert len(expected) == 90
    assert tokens == expected
    assert len(set(tokens)) == len(tokens)


def test_table_light_values_match_sheet():
    rows = _real_rows()
    assert [row[1] for row in rows] == [_code(value) for _, value in _root_tokens()]


def test_table_dark_values_match_sheet():
    dark = _forced_dark_tokens()
    rows = {row[0]: row for row in _real_rows()}
    for name, _ in _root_tokens():
        expected = _code(dark[name]) if name in dark else "—"
        assert rows[_code(name)][2] == expected, name
    assert rows["`--pjx-space-1`"][2] == "—"
    assert rows["`--pjx-color-surface`"][1] == "`#ffffff`"
    assert rows["`--pjx-color-surface`"][2] == "`#18181b`"
    assert rows["`--pjx-shadow-sm`"][2] == "`0 1px 2px rgb(0 0 0 / 0.35)`"


def test_media_dark_block_matches_forced_dark_block():
    # The page documents one dark column; that is only truthful if the
    # prefers-color-scheme block and the forced-dark block agree exactly.
    assert _media_dark_tokens() == _forced_dark_tokens()
    assert _forced_dark_tokens()


def test_value_with_pipe_is_escaped():
    css = (
        ":root {\n  --pjx-odd: a|b;\n}\n\n"
        '[data-pjx-theme="dark"] {\n  --pjx-odd: c|d;\n}\n'
    )
    table = hooks.theme_token_table(css)
    assert "`a\\|b`" in table
    assert "`c\\|d`" in table
    assert _rows(table) == [["`--pjx-odd`", "`a\\|b`", "`c\\|d`"]]


def test_values_are_kept_verbatim():
    rows = {row[0]: row for row in _real_rows()}
    assert rows["`--pjx-font-family-sans`"][1] == (
        '`system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`'
    )
    assert rows["`--pjx-font-family-sans`"][2] == "—"


def test_missing_root_block_raises():
    css = '[data-pjx-theme="dark"] {\n  --pjx-a: 1;\n}\n'
    with pytest.raises(ValueError, match=re.escape(":root")):
        hooks.theme_token_table(css)


def test_missing_dark_block_raises():
    css = ":root {\n  --pjx-a: 1;\n}\n"
    with pytest.raises(ValueError, match=re.escape('[data-pjx-theme="dark"]')):
        hooks.theme_token_table(css)


def test_dark_only_token_raises():
    css = ':root {\n  --pjx-a: 1;\n}\n\n[data-pjx-theme="dark"] {\n  --pjx-b: 2;\n}\n'
    with pytest.raises(ValueError, match="--pjx-b"):
        hooks.theme_token_table(css)


class FakeFile:
    src_path = "reference/theme-tokens.md"


class FakePage:
    file = FakeFile()
    url = "reference/theme-tokens/"


def _hook(markdown: str) -> str:
    return hooks.on_page_markdown(markdown, page=FakePage(), config={}, files=None)


def test_marker_becomes_table():
    out = _hook("intro\n\n<!-- theme-tokens -->\n\nafter")
    assert "theme-tokens -->" not in out
    assert _HEADER in out
    assert "`--pjx-space-1`" in out
    assert out.startswith("intro\n\n") and out.endswith("\n\nafter")


def test_hook_inserts_table_verbatim():
    out = _hook("before\n<!-- theme-tokens -->\nafter")
    assert out == f"before\n{hooks.theme_token_table(_sheet())}\nafter"


def test_marker_spacing_is_tolerated():
    for marker in ("<!--theme-tokens-->", "<!--   theme-tokens   -->"):
        assert _HEADER in _hook(marker), marker


def test_page_without_marker_is_unchanged():
    markdown = "# Title\n\nplain text, no markers here.\n"
    assert _hook(markdown) == markdown


def test_demo_and_token_markers_both_replaced():
    out = _hook("<!-- demo: PJXBadge -->\n\n<!-- theme-tokens -->\n")
    assert "<!--" not in out
    assert '<iframe src="../../demos/pjx-badge.html"' in out
    assert _HEADER in out


_PAGE = _DOCS / "reference" / "theme-tokens.md"


def test_reference_page_has_one_marker():
    text = _PAGE.read_text(encoding="utf-8")
    assert len(re.findall(r"<!--\s*theme-tokens\s*-->", text)) == 1
    # A hand-written row would be a stale copy of the generated table.
    assert not any(line.startswith("| `--pjx-") for line in text.splitlines())


def test_reference_page_is_in_nav():
    nav = (_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "Theme Tokens: reference/theme-tokens.md" in nav


def test_theming_guide_links_reference():
    guide = (_DOCS / "guide" / "theming.md").read_text(encoding="utf-8")
    assert "../reference/theme-tokens.md" in guide
