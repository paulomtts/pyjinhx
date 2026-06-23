"""Structural guards for the component-centric docs layout.

Every demo'd component's section on ``components.md`` must carry an HTML tag
example and a Python constructor example; every component section must carry an
HTML example; and the old per-component theming appendix must be gone (tokens
live in-section, inside the per-component accordions).
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
sys.path.insert(0, str(DOCS))
from demos import DEMOS  # noqa: E402


def _component_sections(text):
    """``### PJXName`` body up to the next ``##``/``###`` heading."""
    parts = re.split(r"^### (PJX\w+)\s*$", text, flags=re.M)
    sections = {}
    for i in range(1, len(parts), 2):
        body = parts[i + 1]
        # stop the body at the next group (``## ``) heading if one slipped in
        sections[parts[i]] = re.split(r"^## ", body, flags=re.M)[0]
    return sections


def test_component_sections_have_html_and_python():
    sections = _component_sections((DOCS / "components.md").read_text(encoding="utf-8"))
    missing = []
    for name in DEMOS:
        sec = sections.get(name, "")
        if "```html" not in sec:
            missing.append(f"{name}: no ```html example")
        if "```python" not in sec:
            missing.append(f"{name}: no ```python example")
    assert not missing, "\n".join(missing)


def test_theming_appendix_removed():
    text = (DOCS / "components.md").read_text(encoding="utf-8")
    assert "## Theming tokens" not in text
    assert "tokens](#" not in text  # no "see [PJXFoo tokens](#...)" cross-refs remain


def test_component_entries_have_html():
    text = (DOCS / "components.md").read_text(encoding="utf-8")
    entries = re.split(r"^### (PJX\w+)\s*$", text, flags=re.M)
    missing = [
        entries[i]
        for i in range(1, len(entries), 2)
        if "```html" not in re.split(r"^## ", entries[i + 1], flags=re.M)[0]
    ]
    assert not missing, f"component entries missing an HTML block: {missing}"
