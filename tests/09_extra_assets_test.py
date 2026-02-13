from tests.ui.unified_component import UnifiedComponent

CSS = "<style>.test-component { color: red; }\n</style>\n"


def test_multiple_extra_js_files():
    component = UnifiedComponent(
        id="multi-js-1",
        text="Multiple JS",
        js=["tests/ui/extra_script.js", "tests/ui/extra_script.js"]
    )

    rendered = component.render()

    expected = (
        CSS
        + '<div id="multi-js-1" class="test-component">\n'
        '    <div class="text">Multiple JS</div>\n'
        "</div>\n"
        "\n"
        "<script>console.log('Button loaded');</script>\n"
        "<script>console.log('Extra script loaded');\n"
        "\n"
        "</script>"
    )

    assert rendered == expected
