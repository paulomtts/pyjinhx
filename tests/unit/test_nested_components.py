import os
import re

from pyjinhx.assets import asset_token
from pyjinhx.finder import Finder
from tests.ui.unified_component import UnifiedComponent

_UI_DIR = Finder.get_class_directory(UnifiedComponent)
_CSS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.css"))
_JS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.js"))

CSS = f'<style data-pjx-asset="{_CSS_TOKEN}">.test-component {{ color: red; }}\n</style>\n'
JS = f'\n<script data-pjx-asset="{_JS_TOKEN}">console.log(\'Button loaded\');</script>'


def test_simple_nesting():
    nested = UnifiedComponent(id="action-btn-1", text="Click Me")
    component = UnifiedComponent(
        id="wrapper-1",
        title="My Wrapper",
        nested=nested,
    )

    rendered = component._render()

    expected = (
        CSS + '<div id="wrapper-1" class="test-component">\n'
        "    <h2>My Wrapper</h2>\n"
        '    <div class="nested">\n'
        "        <p>Nested component ID: action-btn-1</p>\n"
        "        <p>Nested component text: Click Me</p>\n"
        '        <div id="action-btn-1" class="test-component">\n'
        '    <div class="text">Click Me</div>\n'
        "</div>\n"
        "\n"
        "    </div>\n</div>\n" + JS
    )

    assert rendered == expected


def test_component_reuse():
    shared_component = UnifiedComponent(id="shared-1", text="Shared Component")

    component = UnifiedComponent(
        id="parent-1",
        title="Parent",
        items=[shared_component, shared_component, shared_component],
    )

    rendered = str(component.render())

    # Count structural occurrences: id="shared-1" in element attributes, not text or scripts
    id_occurrences = re.findall(r'id="shared-1"', rendered)
    assert len(id_occurrences) == 3, (
        f"Expected exactly 3 id=\"shared-1\" element attributes, got {len(id_occurrences)}"
    )
    assert "Shared Component" in rendered
