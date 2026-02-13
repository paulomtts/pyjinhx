from tests.ui.unified_component import UnifiedComponent


def test_dict_component():
    action_component = UnifiedComponent(id="action-btn", text="Click Me")

    component = UnifiedComponent(
        id="wrapper-1",
        title="My Wrapper",
        sections={
            "header": "Welcome",
            "action": action_component,
            "footer": "Thank you"
        }
    )

    rendered = component._render()

    expected = (
        '<div id="wrapper-1" class="test-component">\n'
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
        "</div>\n"
        "\n"
        "<script>console.log('Button loaded');</script>"
    )

    assert rendered == expected
