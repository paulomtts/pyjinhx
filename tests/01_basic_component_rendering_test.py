import pytest

from tests.ui.unified_component import UnifiedComponent

CSS = "<style>.test-component { color: red; }\n</style>\n"
JS = "\n<script>console.log('Button loaded');</script>"


@pytest.mark.parametrize(
    ("component_id", "text"),
    [
        ("simple-1", "Hello World"),
        ("test-button", "Click Me"),
    ],
)
def test_basic_rendering(component_id: str, text: str):
    component = UnifiedComponent(id=component_id, text=text)
    rendered = component._render()
    expected = (
        CSS
        + f'<div id="{component_id}" class="test-component">\n'
        f'    <div class="text">{text}</div>\n'
        "</div>\n"
        + JS
    )

    assert str(rendered) == expected


def test_html_method():
    component = UnifiedComponent(id="auto-1", text="Auto Render")

    rendered = component.__html__()

    expected = (
        CSS
        + '<div id="auto-1" class="test-component">\n'
        '    <div class="text">Auto Render</div>\n'
        "</div>\n"
        + JS
    )

    assert rendered == expected
