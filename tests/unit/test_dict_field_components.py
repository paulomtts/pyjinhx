import os

from pyjinhx.assets import asset_token
from pyjinhx.finder import Finder
from tests.ui.unified_component import UnifiedComponent

_UI_DIR = Finder.get_class_directory(UnifiedComponent)
_CSS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.css"))
_JS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.js"))

CSS = f'<style data-pjx-asset="{_CSS_TOKEN}">.test-component {{ color: red; }}\n</style>\n'
JS = f'\n<script data-pjx-asset="{_JS_TOKEN}">console.log(\'Button loaded\');</script>'


def test_dict_component():
    action_component = UnifiedComponent(id="action-btn", text="Click Me")

    component = UnifiedComponent(
        id="wrapper-1",
        title="My Wrapper",
        sections={
            "header": "Welcome",
            "action": action_component,
            "footer": "Thank you",
        },
    )

    rendered = component._render()

    expected = (
        CSS + '<div id="wrapper-1" class="test-component">\n'
        "    <h2>My Wrapper</h2>\n"
        '    <div class="sections">\n'
        "        \n"
        '        <div class="section-header">\n'
        "            Welcome\n"
        "        </div>\n"
        "        \n"
        '        <div class="section-action">\n'
        '            <div id="action-btn" class="test-component">\n'
        '    <div class="text">Click Me</div>\n'
        "</div>\n"
        "\n"
        "        </div>\n"
        "        \n"
        '        <div class="section-footer">\n'
        "            Thank you\n"
        "        </div>\n"
        "        \n"
        "    </div>\n"
        "</div>\n" + JS
    )

    assert rendered == expected
