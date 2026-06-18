import os

from pyjinhx.assets import asset_token
from pyjinhx.finder import Finder
from tests.ui.unified_component import UnifiedComponent

_UI_DIR = Finder.get_class_directory(UnifiedComponent)
_CSS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.css"))
_JS_TOKEN = asset_token(os.path.join(_UI_DIR, "unified-component.js"))

CSS = f'<style data-pjx-asset="{_CSS_TOKEN}">.test-component {{ color: red; }}\n</style>\n'
JS = f'\n<script data-pjx-asset="{_JS_TOKEN}">console.log(\'Button loaded\');</script>'


def test_empty_list():
    component = UnifiedComponent(id="empty-list-1", title="Empty List", items=[])

    rendered = component.render()

    expected = (
        CSS + '<div id="empty-list-1" class="test-component">\n'
        "    <h2>Empty List</h2>\n"
        "</div>\n" + JS
    )

    assert rendered == expected


def test_empty_dict():
    component = UnifiedComponent(id="empty-dict-1", title="Empty Dict", sections={})

    rendered = component.render()

    expected = (
        CSS + '<div id="empty-dict-1" class="test-component">\n'
        "    <h2>Empty Dict</h2>\n"
        "</div>\n" + JS
    )

    assert rendered == expected


def test_component_with_only_id():
    component = UnifiedComponent(id="minimal-1")

    rendered = component.render()

    expected = CSS + '<div id="minimal-1" class="test-component">\n</div>\n' + JS

    assert rendered == expected


def test_none_values_in_nested():
    component = UnifiedComponent(
        id="none-values-1", title="None Values", nested=None, items=None, sections=None
    )

    rendered = component.render()

    expected = (
        CSS + '<div id="none-values-1" class="test-component">\n'
        "    <h2>None Values</h2>\n"
        "</div>\n" + JS
    )

    assert rendered == expected
