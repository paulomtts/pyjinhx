from pyjinhx import BaseComponent


def test_generic_component_with_extra_html():
    component = BaseComponent(
        id="generic-1",
        title="test",
        html=["tests/ui/generic_template.html"]
    )
    
    rendered = component.render()
    
    assert 'id="generic-1"' in str(rendered)
    assert "<h1>test</h1>" in str(rendered)
    assert "<div" in str(rendered)


def test_generic_component_with_multiple_html_files():
    component = BaseComponent(
        id="generic-2",
        title="Multiple Files",
        html=["tests/ui/generic_template.html", "tests/ui/extra_content.html"]
    )
    
    rendered = component.render()
    
    assert 'id="generic-2"' in str(rendered)
    assert "<h1>Multiple Files</h1>" in str(rendered)
    assert "Extra HTML Content" in str(rendered)

