from tests.ui.unified_component import UnifiedComponent


def test_simple_nesting():
    nested = UnifiedComponent(id="action-btn-1", text="Click Me")
    component = UnifiedComponent(
        id="wrapper-1",
        title="My Wrapper",
        nested=nested,
    )

    rendered = component._render()

    expected = (
        "<script>console.log('Button loaded');</script>\n"
        '<div id="wrapper-1" class="test-component">\n'
        "    <h2>My Wrapper</h2>\n"
        '    <div class="nested">\n'
        "        <p>Nested component ID: action-btn-1</p>\n"
        "        <p>Nested component text: Click Me</p>\n"
        '        <div id="action-btn-1" class="test-component">\n'
        '    <div class="text">Click Me</div>\n'
        "</div>\n"
        "\n"
        "    </div>\n</div>\n"
    )

    assert rendered == expected


def test_component_reuse():
    shared_component = UnifiedComponent(id="shared-1", text="Shared Component")

    component = UnifiedComponent(
        id="parent-1",
        title="Parent",
        items=[shared_component, shared_component, shared_component],
    )

    rendered = component.render()

    assert "shared-1" in str(rendered)
    assert str(rendered).count("shared-1") >= 3
    assert "Shared Component" in str(rendered)
