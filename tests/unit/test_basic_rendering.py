import pytest
from markupsafe import Markup

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
        CSS + f'<div id="{component_id}" class="test-component">\n'
        f'    <div class="text">{text}</div>\n'
        "</div>\n" + JS
    )

    assert str(rendered) == expected


def test_html_method():
    component = UnifiedComponent(id="auto-1", text="Auto Render")

    html_result = component.__html__()
    render_result = component.render()

    expected = (
        CSS + '<div id="auto-1" class="test-component">\n'
        '    <div class="text">Auto Render</div>\n'
        "</div>\n" + JS
    )

    assert html_result == expected
    assert isinstance(html_result, Markup), "__html__() must return markupsafe.Markup"
    assert isinstance(render_result, Markup), "render() must return markupsafe.Markup"
