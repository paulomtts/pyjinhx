import pytest

from tests.ui.unified_component import UnifiedComponent


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
        f'<div id="{component_id}" class="test-component">\n'
        f'    <div class="text">{text}</div>\n'
        "</div>\n"
        "\n<script>console.log('Button loaded');</script>"
    )

    assert str(rendered) == expected


def test_html_method():
    component = UnifiedComponent(id="auto-1", text="Auto Render")

    rendered = component.__html__()

    assert (
        rendered
        == """<div id="auto-1" class="test-component">
    <div class="text">Auto Render</div>
</div>

<script>console.log('Button loaded');</script>"""
    )
