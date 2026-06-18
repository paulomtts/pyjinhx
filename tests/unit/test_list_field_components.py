import os

from pyjinhx.assets import asset_token
from pyjinhx.finder import Finder
from tests.ui.unified_component import UnifiedComponent

_UI_DIR = Finder.get_class_directory(UnifiedComponent)
_CSS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.css"))
_JS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.js"))

CSS = f'<style data-pjx-asset="{_CSS_TOKEN}">.test-component {{ color: red; }}\n</style>\n'
JS = f'\n<script data-pjx-asset="{_JS_TOKEN}">console.log(\'Button loaded\');</script>'


def test_nested_list_of_components():
    item1 = UnifiedComponent(id="btn-1", text="First Button")
    item2 = UnifiedComponent(id="btn-2", text="Second Button")
    item3 = UnifiedComponent(id="btn-3", text="Third Button")

    component = UnifiedComponent(
        id="list-1", title="Action Buttons", items=[item1, item2, item3]
    )

    rendered = component._render()

    expected = (
        CSS + '<div id="list-1" class="test-component">\n'
        "    <h2>Action Buttons</h2>\n"
        '    <div class="items">\n'
        "        <ul>\n"
        "            \n"
        '            <li><div id="btn-1" class="test-component">\n'
        '    <div class="text">First Button</div>\n'
        "</div>\n"
        "</li>\n"
        "            \n"
        '            <li><div id="btn-2" class="test-component">\n'
        '    <div class="text">Second Button</div>\n'
        "</div>\n"
        "</li>\n"
        "            \n"
        '            <li><div id="btn-3" class="test-component">\n'
        '    <div class="text">Third Button</div>\n'
        "</div>\n"
        "</li>\n"
        "            \n"
        "        </ul>\n"
        "    </div>\n"
        "</div>\n" + JS
    )

    assert rendered == expected
