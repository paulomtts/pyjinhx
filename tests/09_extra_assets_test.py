from tests.ui.unified_component import UnifiedComponent


def test_multiple_extra_js_files():
    component = UnifiedComponent(
        id="multi-js-1",
        text="Multiple JS",
        js=["tests/ui/extra_script.js", "tests/ui/extra_script.js"]
    )

    rendered = component.render()

    expected = (
        '<div id="multi-js-1" class="test-component">\n'
        '    <div class="text">Multiple JS</div>\n'
        "</div>\n"
        "\n"
        "<script>console.log('Button loaded');\n"
        "console.log('Extra script loaded');\n"
        "\n"
        "</script>"
    )

    assert rendered == expected
