"""Structural guards for the component-centric docs layout.

Every demo'd component's guide section must carry an HTML tag example and a
Python constructor example; every gallery entry must carry an HTML example; and
the old per-component theming appendix must be gone (tokens live in-section).
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
sys.path.insert(0, str(DOCS))
from demos import DEMOS  # noqa: E402


def _h2_sections(text):
    parts = re.split(r"^## (PJX\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def test_guide_sections_have_html_and_python():
    sections = _h2_sections((DOCS / "guide" / "builtins.md").read_text(encoding="utf-8"))
    missing = []
    for name in DEMOS:
        sec = sections.get(name, "")
        if "```html" not in sec:
            missing.append(f"{name}: no ```html example")
        if "```python" not in sec:
            missing.append(f"{name}: no ```python example")
    assert not missing, "\n".join(missing)


def test_theming_appendix_removed():
    text = (DOCS / "guide" / "builtins.md").read_text(encoding="utf-8")
    assert "## Theming tokens" not in text
    assert "tokens](#" not in text  # no "see [PJXFoo tokens](#...)" cross-refs remain


def test_gallery_entries_have_html():
    text = (DOCS / "gallery.md").read_text(encoding="utf-8")
    entries = re.split(r"^### \[", text, flags=re.M)
    missing = [e.split("]")[0] for e in entries[1:] if "```html" not in e]
    assert not missing, f"gallery entries missing an HTML block: {missing}"
