from tests.ui.unified_component import UnifiedComponent

CSS = "<style>.test-component { color: red; }\n</style>\n"
JS = "\n<script>console.log('Button loaded');</script>"


def test_mixed_list_content():
    item1 = UnifiedComponent(id="btn-1", text="First Button")
    item2 = UnifiedComponent(id="btn-2", text="Second Button")

    component = UnifiedComponent(
        id="mixed-list-1",
        title="Mixed List",
        items=["String Item 1", item1, "String Item 2", item2, "String Item 3"]
    )

    rendered = component.render()

    expected = (
        CSS
        + '<div id="mixed-list-1" class="test-component">\n'
        "    <h2>Mixed List</h2>\n"
        '    <div class="items">\n'
        "        <ul>\n"
        "            \n"
        "            <li>String Item 1</li>\n"
        "            \n"
        '            <li><div id="btn-1" class="test-component">\n'
        '    <div class="text">First Button</div>\n'
        "</div>\n"
        "</li>\n"
        "            \n"
        "            <li>String Item 2</li>\n"
        "            \n"
        '            <li><div id="btn-2" class="test-component">\n'
        '    <div class="text">Second Button</div>\n'
        "</div>\n"
        "</li>\n"
        "            \n"
        "            <li>String Item 3</li>\n"
        "            \n"
        "        </ul>\n"
        "    </div>\n"
        "</div>\n"
        + JS
    )

    assert rendered == expected


def test_mixed_dict_content():
    action_component = UnifiedComponent(id="action-btn", text="Click Me")
    footer_component = UnifiedComponent(id="footer-btn", text="Footer")

    component = UnifiedComponent(
        id="mixed-dict-1",
        title="Mixed Dict",
        sections={
            "header": "Welcome Text",
            "action": action_component,
            "middle": "Middle Text",
            "footer": footer_component,
            "end": "End Text"
        }
    )

    rendered = component.render()

    expected = (
        CSS
        + '<div id="mixed-dict-1" class="test-component">\n'
        "    <h2>Mixed Dict</h2>\n"
        '    <div class="sections">\n'
        "        \n"
        '        <div class="section-header">\n'
        "            Welcome Text\n"
        "        </div>\n"
        "        \n"
        '        <div class="section-action">\n'
        '            <div id="action-btn" class="test-component">\n'
        '    <div class="text">Click Me</div>\n'
        "</div>\n"
        "\n"
        "        </div>\n"
        "        \n"
        '        <div class="section-middle">\n'
        "            Middle Text\n"
        "        </div>\n"
        "        \n"
        '        <div class="section-footer">\n'
        '            <div id="footer-btn" class="test-component">\n'
        '    <div class="text">Footer</div>\n'
        "</div>\n"
        "\n"
        "        </div>\n"
        "        \n"
        '        <div class="section-end">\n'
        "            End Text\n"
        "        </div>\n"
        "        \n"
        "    </div>\n"
        "</div>\n"
        + JS
    )

    assert rendered == expected
