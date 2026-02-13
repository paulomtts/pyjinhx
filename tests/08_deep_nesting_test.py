from tests.ui.unified_component import UnifiedComponent

CSS = "<style>.test-component { color: red; }\n</style>\n"
JS = "\n<script>console.log('Button loaded');</script>"


def test_3_level_deep_nesting():
    level3 = UnifiedComponent(id="level3-1", text="Level 3 Message")
    level2 = UnifiedComponent(id="level2-1", title="Level 2", nested=level3)
    level1 = UnifiedComponent(id="level1-1", title="Level 1", nested=level2)

    rendered = level1._render()

    expected = (
        CSS
        + '<div id="level1-1" class="test-component">\n'
        "    <h2>Level 1</h2>\n"
        '    <div class="nested">\n'
        "        <p>Nested component ID: level2-1</p>\n"
        "        <p>Nested component text: None</p>\n"
        '        <div id="level2-1" class="test-component">\n'
        "    <h2>Level 2</h2>\n"
        '    <div class="nested">\n'
        "        <p>Nested component ID: level3-1</p>\n"
        "        <p>Nested component text: Level 3 Message</p>\n"
        '        <div id="level3-1" class="test-component">\n'
        '    <div class="text">Level 3 Message</div>\n'
        "</div>\n"
        "\n"
        "    </div>\n"
        "</div>\n"
        "\n"
        "    </div>\n"
        "</div>\n"
        + JS
    )

    assert rendered == expected
