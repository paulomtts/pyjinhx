from tests.ui.unified_component import UnifiedComponent


def test_js_collection_order():
    component = UnifiedComponent(
        id="js-order-1",
        text="JS Order Test",
        js=["tests/ui/extra_script.js"]
    )
    
    rendered = component.render()
    
    script_content = str(rendered).split("<script>")[1].split("</script>")[0]
    
    assert "console.log('Button loaded');" in script_content
    assert "console.log('Extra script loaded');" in script_content
    
    button_index = script_content.find("console.log('Button loaded');")
    extra_index = script_content.find("console.log('Extra script loaded');")
    
    assert button_index < extra_index, "Auto JS should come before extra JS"


def test_js_collection_from_nested_components():
    nested1 = UnifiedComponent(id="nested-js-1", text="Nested 1")
    nested2 = UnifiedComponent(id="nested-js-2", text="Nested 2")
    
    component = UnifiedComponent(
        id="parent-js-1",
        title="Parent",
        items=[nested1, nested2]
    )
    
    rendered = component.render()
    
    script_content = str(rendered).split("<script>")[1].split("</script>")[0]
    
    assert "console.log('Button loaded');" in script_content
    assert script_content.count("console.log('Button loaded');") == 1


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
    
    rendered = component.render()
    
    script_content = str(rendered).split("<script>")[1].split("</script>")[0]
    
    assert "console.log('Button loaded');" in script_content
    assert script_content.count("console.log('Extra script loaded');") == 1

