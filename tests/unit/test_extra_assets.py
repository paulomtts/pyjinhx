import os

from pyjinhx.assets import asset_token
from pyjinhx.finder import Finder
from tests.ui.unified_component import UnifiedComponent

_UI_DIR = Finder.get_class_directory(UnifiedComponent)
_CSS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.css"))
_JS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.js"))
_EXTRA_JS_TOKEN = asset_token("tests/ui/extra_script.js")

CSS = f'<style data-pjx-asset="{_CSS_TOKEN}">.test-component {{ color: red; }}\n</style>\n'


def test_multiple_extra_js_files():
    component = UnifiedComponent(
        id="multi-js-1",
        text="Multiple JS",
        js=["tests/ui/extra_script.js", "tests/ui/extra_script.js"],
    )

    rendered = component.render()

    expected = (
        CSS + '<div id="multi-js-1" class="test-component">\n'
        '    <div class="text">Multiple JS</div>\n'
        "</div>\n"
        f'\n<script data-pjx-asset="{_JS_TOKEN}">console.log(\'Button loaded\');</script>\n'
        f'<script data-pjx-asset="{_EXTRA_JS_TOKEN}">console.log(\'Extra script loaded\');\n'
        "\n"
        "</script>"
    )

    assert rendered == expected
