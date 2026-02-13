from tests.ui.unified_component import UnifiedComponent


def test_js_collection_order():
    component = UnifiedComponent(
        id="js-order-1",
        text="JS Order Test",
        js=["tests/ui/extra_script.js"]
    )

    rendered = str(component.render())

    assert "console.log('Button loaded');" in rendered
    assert "console.log('Extra script loaded');" in rendered

    button_index = rendered.find("console.log('Button loaded');")
    extra_index = rendered.find("console.log('Extra script loaded');")

    assert button_index < extra_index, "Auto JS should come before extra JS"


def test_js_collection_from_nested_components():
    nested1 = UnifiedComponent(id="nested-js-1", text="Nested 1")
    nested2 = UnifiedComponent(id="nested-js-2", text="Nested 2")

    component = UnifiedComponent(
        id="parent-js-1",
        title="Parent",
        items=[nested1, nested2]
    )

    rendered = str(component.render())

    assert "console.log('Button loaded');" in rendered
    assert rendered.count("console.log('Button loaded');") == 1


def test_js_collection_with_extra_js_in_nested():
    nested = UnifiedComponent(
        id="nested-extra-js-1",
        text="Nested with Extra JS",
        js=["tests/ui/extra_script.js"]
    )

    component = UnifiedComponent(
        id="parent-extra-js-1",
        title="Parent",
        nested=nested,
        js=["tests/ui/extra_script.js"]
    )

    rendered = str(component.render())

    assert "console.log('Button loaded');" in rendered
    assert rendered.count("console.log('Extra script loaded');") == 1


def test_separate_script_tags():
    component = UnifiedComponent(
        id="sep-tags-1",
        text="Separate Tags",
        js=["tests/ui/extra_script.js"]
    )

    rendered = str(component.render())

    assert rendered.count("<script>") == 2
    assert rendered.count("</script>") == 2
